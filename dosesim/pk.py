"""Vancomycin PK simulator (DoseSim grader core).

Model: Thomson et al. 2009, J Antimicrob Chemother 63(5):1050-1057, doi:10.1093/jac/dkp085.
Two-compartment IV model. Kidney function (CrCL) drives clearance.
All sourced numbers live in sources/vancomycin.md.

Units used everywhere: mg, L, h, mg/L, mL/min, kg, years.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.linalg import expm

# ---- Thomson 2009 typical values (Table 2) ----
CL_TYP = 2.99          # L/h, at CrCL = 66 mL/min
CRCL_REF = 66.0        # mL/min
CRCL_SLOPE = 0.0154    # fractional change in CL per mL/min of CrCL
V1_PER_KG = 0.675      # L/kg (total body weight)
V2_PER_KG = 0.732      # L/kg (total body weight)
Q_VALUE = 2.28         # unit is an open issue: "L/h" or "h-1" (see VALIDATION.md)

# Between-patient variability, %CV (Table 2). Used only for virtual populations.
IIV_CV = {"CL": 0.27, "V1": 0.15, "V2": 1.30, "Q": 0.49}

# Validated covariate ranges (model-building group). Tasks must stay inside.
VALID_RANGE = {"age": (16, 97), "weight": (40, 159), "crcl": (12, 216)}

# Lowest clearance we allow, so very low CrCL can't give zero or negative CL.
CL_FLOOR = 0.1  # L/h. Below the model's validated range anyway; guards math only.


def cockcroft_gault(age: float, weight_kg: float, scr_mg_dl: float, sex: str) -> float:
    """CrCL in mL/min. Cockcroft-Gault with total body weight (as Thomson used).

    Formula: (140 - age) x weight / (72 x SCr), x 0.85 if female.
    Source: Cockcroft & Gault, Nephron 1976;16:31-41.
    """
    if scr_mg_dl <= 0:
        raise ValueError("serum creatinine must be > 0")
    crcl = (140.0 - age) * weight_kg / (72.0 * scr_mg_dl)
    if sex.lower().startswith("f"):
        crcl *= 0.85
    return crcl


@dataclass
class Params:
    """One patient's PK parameters (for one CrCL value)."""
    CL: float  # L/h
    V1: float  # L
    V2: float  # L
    Q: float   # L/h (always converted to L/h here)


def typical_params(weight_kg: float, crcl: float, q_unit: str = "L/h",
                   eta: dict | None = None) -> Params:
    """Typical-patient parameters, optionally shifted by random effects (eta).

    q_unit:
      "L/h"  -> Q = 2.28 L/h
      "h-1"  -> 2.28 is a rate constant k12, so Q = 2.28 x V1  (the alternative reading)
    eta: log-scale random effects per parameter, e.g. {"CL": 0.1}. None = typical patient.
    """
    eta = eta or {}
    cl = CL_TYP * (1.0 + CRCL_SLOPE * (crcl - CRCL_REF))
    cl = max(cl, CL_FLOOR)
    v1 = V1_PER_KG * weight_kg
    v2 = V2_PER_KG * weight_kg
    if q_unit == "L/h":
        q = Q_VALUE
    elif q_unit == "h-1":
        q = Q_VALUE * v1
    else:
        raise ValueError(f"unknown q_unit {q_unit}")
    # Random effects are log-normal: param x exp(eta)
    return Params(
        CL=cl * np.exp(eta.get("CL", 0.0)),
        V1=v1 * np.exp(eta.get("V1", 0.0)),
        V2=v2 * np.exp(eta.get("V2", 0.0)),
        Q=q * np.exp(eta.get("Q", 0.0)),
    )


@dataclass
class Dose:
    time_h: float      # start of infusion
    amount_mg: float
    duration_h: float  # infusion length

    @property
    def rate(self) -> float:
        return self.amount_mg / self.duration_h


@dataclass
class SimResult:
    times: np.ndarray       # h
    conc: np.ndarray        # mg/L, central compartment
    cum_auc: np.ndarray     # mg*h/L, cumulative from t=0
    doses: list = field(default_factory=list)

    def conc_at(self, t: float) -> float:
        return float(np.interp(t, self.times, self.conc))

    def auc_between(self, t0: float, t1: float) -> float:
        return float(np.interp(t1, self.times, self.cum_auc) - np.interp(t0, self.times, self.cum_auc))

    def auc24_by_day(self, n_days: int) -> list[float]:
        """AUC for each 24 h day (day 0 = 0-24 h)."""
        return [self.auc_between(24 * d, 24 * (d + 1)) for d in range(n_days)]

    def troughs(self, before_h: float | None = None) -> list[float]:
        """Concentration just before each dose after the first (pre-dose levels)."""
        out = []
        for d in self.doses[1:]:
            if before_h is None or d.time_h < before_h:
                out.append(self.conc_at(d.time_h - 1e-6))
        return out


def simulate(doses: list[Dose], weight_kg: float, crcl_by_day: list[float],
             horizon_h: float, q_unit: str = "L/h", eta: dict | None = None,
             dt: float = 0.1) -> SimResult:
    """Simulate central concentration over time.

    Exact solution: the model is linear, so on each piece of time with fixed inputs
    we step it forward with a matrix exponential (no ODE solver error).
    CrCL can change each day (crcl_by_day[d] applies from 24d to 24(d+1) h);
    the last value carries forward.

    State = [amount central (mg), amount peripheral (mg), cumulative AUC (mg*h/L), 1]
    The trailing 1 lets a constant infusion rate sit inside the matrix.
    """
    doses = sorted(doses, key=lambda d: d.time_h)
    # Every moment something changes: infusion start/stop, new day, output grid.
    breaks = {0.0, horizon_h}
    for d in doses:
        breaks.add(d.time_h)
        breaks.add(d.time_h + d.duration_h)
    breaks.update(24.0 * k for k in range(int(horizon_h // 24) + 1))
    grid = np.round(np.arange(0.0, horizon_h + 1e-9, dt), 10)
    breaks.update(grid.tolist())
    pts = np.array(sorted(b for b in breaks if 0.0 <= b <= horizon_h))

    def params_at(t: float) -> Params:
        day = min(int(t // 24), len(crcl_by_day) - 1)
        return typical_params(weight_kg, crcl_by_day[day], q_unit, eta)

    def rate_at(t: float) -> float:
        # Sum of infusions running at time t (start inclusive, end exclusive)
        return sum(d.rate for d in doses if d.time_h <= t < d.time_h + d.duration_h)

    x = np.array([0.0, 0.0, 0.0, 1.0])
    conc = [0.0]
    cum = [0.0]
    for t0, t1 in zip(pts[:-1], pts[1:]):
        h = t1 - t0
        if h <= 0:
            continue
        mid = 0.5 * (t0 + t1)   # inputs are constant inside the piece; sample its middle
        p = params_at(mid)
        r = rate_at(mid)
        k10, k12, k21 = p.CL / p.V1, p.Q / p.V1, p.Q / p.V2
        A = np.array([
            [-(k10 + k12), k21, 0.0, r],     # central: loses to elimination + peripheral, gains infusion
            [k12, -k21, 0.0, 0.0],           # peripheral
            [1.0 / p.V1, 0.0, 0.0, 0.0],     # AUC grows by central concentration
            [0.0, 0.0, 0.0, 0.0],            # constant 1
        ])
        x = expm(A * h) @ x
        p_end = params_at(t1 - 1e-9)
        conc.append(x[0] / p_end.V1)
        cum.append(x[2])

    return SimResult(times=pts, conc=np.array(conc), cum_auc=np.array(cum), doses=doses)


def regimen(first_dose_mg: float, maint_dose_mg: float, interval_h: float,
            horizon_h: float, start_h: float = 0.0,
            infusion_mg_per_h: float = 1000.0) -> list[Dose]:
    """Loading dose at start_h, then maintenance doses every interval_h.

    Infusion length = dose / infusion_mg_per_h (default 1 g per hour: an assumption,
    logged in VALIDATION.md; it barely affects AUC).
    """
    out = [Dose(start_h, first_dose_mg, first_dose_mg / infusion_mg_per_h)]
    t = start_h + interval_h
    while t < horizon_h - 1e-9:
        out.append(Dose(t, maint_dose_mg, maint_dose_mg / infusion_mg_per_h))
        t += interval_h
    return out
