# Grader validation — vancomycin (Thomson 2009)

Date: 2026-10-23. Code: `validation/validate_vancomycin.py`. Raw output: `validation/results_vancomycin.json`.
No expert review yet.

## 1. Does the simulator do the math right?
`tests/test_pk.py` — 7 checks, all pass:
- Cockcroft-Gault matches hand calculation.
- CL = 2.99 L/h exactly at CrCL 66.
- Single dose: total AUC = dose / CL (within 0.1%).
- Steady state: AUC24 = daily dose / CL (within 0.5%).
- Mass balance: everything given is eliminated (within 0.1%).
- Matches an independent ODE solver (scipy `solve_ivp`) within 0.1%.
- Falling kidney function raises troughs (direction check).

## 2. Does it reproduce the paper?
Virtual group shaped like the paper's evaluation group (100 adults, Glasgow):
weight median 65 kg, CrCL median 50 mL/min, dosed with the paper's new guideline.
1,000 patients, seed 20261023. Only CL and V1 vary per patient, as in the paper's own predictions.

| Metric | Paper | DoseSim (Q in L/h) | Gap |
|---|---|---|---|
| Steady-state AUC24, mean | 520 | 499–512* | −2% to −4% |
| Steady-state AUC24, SD | 124 | ~150 | wider |
| % with AUC24/MIC > 400 | 87% | 73–76%* | lower |
| Trough, days 1–4, mean (SD) | 12.2 (3.4) | 11.0 (3.8) | −10% |

*Range across seeds / sample sizes (n = 1,000 and 4,000).

**Key finding:** the paper's "AUC24" is a steady-state value. Its mean Css 21.7 mg/L × 24 h = 520.8,
which matches its reported AUC24 of 520. Compared on that basis, our mean is within 2–4%.

**Why our spread is wider (hypothesis, not proven):** the paper predicted each patient's levels from
individual estimates fitted to that patient's own blood levels. Those estimates are pulled toward the
average ("shrinkage"), which narrows the spread and pushes more patients into range. We sample full
between-patient variability instead. Changing our assumed CrCL spread did not change the result
(tested 0.30–0.50 log-SD: mean 512, SD ~149, 76% > 400 each time).

**Verdict:** the grader reproduces the paper's average exposure. Variability is wider than reported,
for a likely known reason. Acceptable for v0 grading. Flag for expert review.

## 3. Does the paper's dosing table land in the guideline target?
Typical 70 kg patient, middle of each CrCL band, steady state:

| CrCL | Regimen | AUC24 | Trough |
|---|---|---|---|
| 16 | 500 mg q48h | 348 | 11.2 |
| 25 | 500 mg q24h | 450 | 14.9 |
| 35 | 750 mg q24h | 479 | 14.5 |
| 47 | 500 mg q12h | 473 | 15.5 |
| 65 | 750 mg q12h | 510 | 15.2 |
| 82 | 1000 mg q12h | 537 | 14.8 |
| 100 | 1250 mg q12h | 549 | 13.8 |
| 120 | 1500 mg q12h | 548 | 12.5 |

7 of 8 bands land in 400–600. The lowest band (CrCL < 20) lands below 400. That's a property of the
paper's table, not a grader error: it was built for trough targets, before AUC dosing.

## 4. The Q-unit question
The paper's table prints Q in "h-1". Standard NONMEM two-compartment parameterization uses L/h.

| Reading | Trough mean, days 1–4 | Steady-state AUC24 |
|---|---|---|
| Q = 2.28 L/h | 11.0 | identical |
| Q = 2.28 h-1 (×V1 ≈ 100 L/h) | 13.4 | identical |
| Paper | 12.2 | — |

- **Troughs can't settle it.** The paper's value falls between the two readings.
- **AUC can't settle it either,** and that's good news: steady-state AUC = dose/CL doesn't depend on Q.
  Early-day AUCs differ by about 3%.
- **Decision:** use **L/h**. Reasons: standard parameterization; matches InsightRX's implementation;
  the h-1 reading (~100 L/h) would erase the distribution phase the authors chose to model.
- **Safeguard (new quality gate):** a task ships only if its grading verdict is the same under both readings.
  So the open question can't change any score.

## 5. Assumptions logged
| Assumption | Effect tested? |
|---|---|
| Infusion rate 1 g/h | Yes. 600 mg/h changes mean trough by +0.2 mg/L, AUC unchanged |
| Log-normal patient spread, clipped to paper ranges | Yes. No effect on results (Section 2) |
| No correlation between random effects | Not tested. Paper reports none |
| CrCL constant over days 1–4 in the evaluation re-creation | Not tested. Real patients varied |

## 6. Still open
1. **Safety threshold** (AUC linked to kidney injury): not sourced. Safety part of reward stays off.
2. Guideline target (400–600): confirm in the guideline's full text.
3. Expert review of this whole file.
