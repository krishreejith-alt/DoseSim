"""Checks that the simulator does the math right (not that the model is right — see VALIDATION.md)."""

import numpy as np
from scipy.integrate import solve_ivp

from dosesim.pk import Dose, cockcroft_gault, regimen, simulate, typical_params


def test_cockcroft_gault_known_values():
    # (140-40)*70/(72*1.0) = 97.22
    assert abs(cockcroft_gault(40, 70, 1.0, "M") - 97.2222) < 1e-3
    # Female = x0.85
    assert abs(cockcroft_gault(40, 70, 1.0, "F") - 97.2222 * 0.85) < 1e-3


def test_cl_equation_at_reference():
    # At CrCL 66 the typical CL must equal 2.99 L/h exactly
    assert abs(typical_params(70, 66).CL - 2.99) < 1e-12


def test_single_dose_total_auc_equals_dose_over_cl():
    # Basic PK law: total AUC = dose / CL (for linear elimination)
    p = typical_params(70, 100)
    r = simulate([Dose(0, 1000, 1)], 70, [100], horizon_h=24 * 20)
    assert abs(r.cum_auc[-1] - 1000 / p.CL) / (1000 / p.CL) < 1e-3


def test_steady_state_auc24_equals_daily_dose_over_cl():
    # At steady state, AUC over 24 h = daily dose / CL
    p = typical_params(80, 70)
    doses = regimen(1000, 1000, 12, horizon_h=24 * 15)
    r = simulate(doses, 80, [70], horizon_h=24 * 15)
    assert abs(r.auc24_by_day(15)[-1] - 2000 / p.CL) / (2000 / p.CL) < 5e-3


def test_mass_balance():
    # Give 3 days of doses, then wait 30 days: everything given must be eliminated (CL x AUC)
    p = typical_params(60, 50)
    doses = regimen(1500, 750, 12, horizon_h=72)
    r = simulate(doses, 60, [50], horizon_h=24 * 33, dt=1.0)
    eliminated = p.CL * r.cum_auc[-1]
    total_given = sum(d.amount_mg for d in doses)
    assert abs(eliminated - total_given) / total_given < 1e-3


def test_matches_independent_ode_solver():
    # Cross-check exact solution against a standard numerical ODE solver
    w, crcl = 75, 60
    p = typical_params(w, crcl)
    doses = regimen(1500, 1000, 12, horizon_h=48)

    def rate(t):
        return sum(d.rate for d in doses if d.time_h <= t < d.time_h + d.duration_h)

    def f(t, y):
        a1, a2 = y
        return [rate(t) - (p.CL + p.Q) / p.V1 * a1 + p.Q / p.V2 * a2,
                p.Q / p.V1 * a1 - p.Q / p.V2 * a2]

    t_eval = np.array([0.5, 1.0, 6.0, 11.99, 12.5, 30.0, 47.9])
    sol = solve_ivp(f, (0, 48), [0, 0], t_eval=t_eval, max_step=0.05, rtol=1e-8, atol=1e-8)
    r = simulate(doses, w, [crcl], horizon_h=48, dt=0.01)
    ours = np.array([r.conc_at(t) for t in t_eval])
    ref = sol.y[0] / p.V1
    assert np.max(np.abs(ours - ref) / ref) < 1e-3


def test_worse_kidney_function_raises_trough():
    # Same doses; kidney function drops on day 2 -> later troughs must be higher
    doses = regimen(1500, 1000, 12, horizon_h=96)
    stable = simulate(doses, 70, [80, 80, 80, 80], horizon_h=96)
    falling = simulate(doses, 70, [80, 40, 25, 25], horizon_h=96)
    assert falling.troughs()[-1] > stable.troughs()[-1]
