"""Grader validation for vancomycin (Thomson 2009).

Re-creates the paper's evaluation in silico and compares to its reported numbers.
Also settles the Q-unit question by running both readings.

Run:  python3 -m validation.validate_vancomycin
Output: printed tables + validation/results_vancomycin.json
"""

import json
from pathlib import Path

import numpy as np

from dosesim.pk import IIV_CV, regimen, simulate, typical_params

RNG_SEED = 20261023
N_PATIENTS = 1000
HORIZON = 96.0  # first 4 days, as in the paper's evaluation

# Paper's reported values (Thomson 2009, evaluation group, new guideline). See sources/vancomycin.md.
REPORTED = {"auc24_mean": 520, "auc24_sd": 124, "trough_mean": 12.2, "trough_sd": 3.4,
            "pct_auc_over_400": 87}

# Paper's new maintenance table: (CrCL upper bound, dose mg, interval h)
MAINT_TABLE = [(20, 500, 48), (30, 500, 24), (40, 750, 24), (55, 500, 12),
               (75, 750, 12), (90, 1000, 12), (110, 1250, 12), (1e9, 1500, 12)]


def maintenance(crcl):
    for upper, dose, tau in MAINT_TABLE:
        if crcl < upper:
            return dose, tau
    raise AssertionError


def loading(weight):
    return 1000 if weight < 60 else (1500 if weight <= 90 else 2000)


def omega(cv):
    # %CV -> SD of log-normal random effect
    return np.sqrt(np.log(1 + cv ** 2))


def make_population(rng, n):
    """Virtual patients shaped like the paper's evaluation group.

    Paper gives only medians and ranges: weight 65 (35-130) kg, CrCL 50 (12-148) mL/min.
    ASSUMPTION: log-normal spread, clipped to those ranges (weight floor 40 = model's valid range).
    """
    w = np.clip(65 * np.exp(rng.normal(0, 0.28, n)), 40, 130)
    c = np.clip(50 * np.exp(rng.normal(0, 0.50, n)), 12, 148)
    return w, c


def run(q_unit, iiv_on, infusion_mg_per_h=1000.0, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    w, c = make_population(rng, N_PATIENTS)
    aucs, auc_d4, troughs, over400, ss = [], [], [], [], []
    for wi, ci in zip(w, c):
        eta = {k: rng.normal(0, omega(IIV_CV[k])) for k in iiv_on}
        dose, tau = maintenance(ci)
        doses = regimen(loading(wi), dose, tau, HORIZON, infusion_mg_per_h=infusion_mg_per_h)
        r = simulate(doses, wi, [ci], HORIZON, q_unit=q_unit, eta=eta, dt=0.25)
        day_aucs = r.auc24_by_day(4)
        aucs.extend(day_aucs)
        auc_d4.append(day_aucs[-1])
        over400.append(day_aucs[-1] > 400)
        troughs.extend(r.troughs(before_h=HORIZON))
        # Steady-state AUC24 = daily dose / CL. The paper's "AUC24" is this (Css 21.7 x 24 = 520.8).
        ss.append(dose * 24 / tau / typical_params(wi, ci, q_unit, eta).CL)
    return {
        "q_unit": q_unit, "iiv_on": list(iiv_on), "infusion_mg_per_h": infusion_mg_per_h,
        "auc24_mean": float(np.mean(aucs)), "auc24_sd": float(np.std(aucs)),
        "auc24_day4_mean": float(np.mean(auc_d4)),
        "trough_mean": float(np.mean(troughs)), "trough_sd": float(np.std(troughs)),
        "pct_auc_over_400_day4": float(100 * np.mean(over400)),
        "ss_auc24_mean": float(np.mean(ss)), "ss_auc24_sd": float(np.std(ss)),
        "pct_ss_auc_over_400": float(100 * np.mean(np.array(ss) > 400)),
    }


def table_check():
    """Typical 70 kg patient at the middle of each CrCL band: steady-state AUC24 and trough."""
    rows = []
    for crcl in [16, 25, 35, 47, 65, 82, 100, 120]:
        dose, tau = maintenance(crcl)
        doses = regimen(dose, dose, tau, 24 * 20)
        r = simulate(doses, 70, [crcl], 24 * 20, dt=0.25)
        last_day = r.auc24_by_day(20)[-1]
        if tau == 48:  # 48 h interval: average the last two days
            last_day = np.mean(r.auc24_by_day(20)[-2:])
        rows.append({"crcl": crcl, "dose_mg": dose, "interval_h": tau,
                     "ss_auc24": round(float(last_day), 1),
                     "ss_trough": round(r.troughs()[-1], 1)})
    return rows


def main():
    results = {"reported": REPORTED, "runs": [], "table_check": table_check()}
    # Primary: mirror the paper (only CL and V1 varied per patient; V2, Q fixed)
    for q_unit in ["L/h", "h-1"]:
        results["runs"].append(run(q_unit, ["CL", "V1"]))
    # Sensitivity: full variability; slower infusion (10 mg/min = 600 mg/h)
    results["runs"].append(run("L/h", ["CL", "V1", "V2", "Q"]))
    results["runs"].append(run("L/h", ["CL", "V1"], infusion_mg_per_h=600.0))

    print("Reported (paper):", REPORTED)
    for r in results["runs"]:
        print(r)
    print("Guideline table check (70 kg, steady state):")
    for row in results["table_check"]:
        print(row)
    out = Path(__file__).parent / "results_vancomycin.json"
    out.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
