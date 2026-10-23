# Vancomycin — sources for DoseSim drug #1

Status: draft v0.1, 2026-10-23. No expert review yet (`reviewed_by: pending`).
Rule: every number below has a source. Anything not yet checked is marked **UNVERIFIED**.

---

## 1. Grader model (PK model)

**Source (primary, read directly):**
Thomson AH, Staatz CE, Tobin CM, Gall M, Lovering AM. Development and evaluation of
vancomycin dosage guidelines designed to achieve new target concentrations.
*J Antimicrob Chemother.* 2009;63(5):1050–1057. doi:10.1093/jac/dkp085
Open-access copy: https://strathprints.strath.ac.uk/13001/

### What the model is
- Two-compartment IV model. Fitted in NONMEM (FOCE with interaction).
- Clearance (CL) depends on kidney function (CrCL).
- Central (V1) and peripheral (V2) volumes scale with total body weight.

### Parameters (Table 2 of the paper)
| Parameter | Value | Notes |
|---|---|---|
| CL | 2.99 L/h | Typical value at CrCL = 66 mL/min |
| CrCL effect on CL | 0.0154 per mL/min | ≈15.4% change in CL per 10 mL/min |
| V1 | 0.675 L/kg | × total body weight |
| V2 | 0.732 L/kg | × total body weight |
| Q | 2.28 | **Unit printed as "h-1" in the table. See Open issue 1.** |

CL equation as we implement it (paper gives the relationship in words, not a printed formula):
`CL = 2.99 × (1 + 0.0154 × (CrCL − 66))`  — CrCL in mL/min

### Variability and error (for realistic virtual patients)
| Item | Value |
|---|---|
| Between-patient variability (%CV) | CL 27, V1 15, V2 130, Q 49 |
| Residual error | additive 1.6 mg/L + proportional 15% |

### How CrCL must be calculated
Cockcroft-Gault using **total body weight**. Tasks must use the same equation, or the grader is invalid.

### Validated range (hard limit for tasks)
From the model-building group (398 adults, 1,557 concentrations):

| Covariate | Median (range) |
|---|---|
| Age | 66 (16–97) years |
| Weight | 72 (40–159) kg |
| CrCL | 64 (12–216) mL/min |

**Excluded from the source data → excluded from our tasks:** patients on dialysis or
other renal replacement therapy.
Our v0 tasks stay inside: adults 18–97 y, 40–159 kg, CrCL 12–216 mL/min, no dialysis.
(18 not 16: v0 scope is adults only.)

### Known limits (stated by the authors)
- Data were mostly retrospective routine monitoring records.
- Their evaluation used *predicted*, not observed, concentrations.
- ~19% of patients had BMI > 30; authors advise care in obese and underweight patients.
- Wide variability within and between patients.

### Cross-check
InsightRX's public model library (github.com/InsightRX/PKPDmodels, `pk_vanco_thomson.json5`)
lists the same CL, CrCL coefficient, V1, V2 and Q values and treats Q as L/h.
That repo shows no license → used **only** as a cross-check. No code copied.

---

## 2. Dosing target (what "correct" means)

**Source (primary):**
Rybak MJ, Le J, Lodise TP, et al. Therapeutic monitoring of vancomycin for serious
methicillin-resistant *Staphylococcus aureus* infections: a revised consensus guideline and
review by ASHP, IDSA, PIDS and SIDP. *Am J Health Syst Pharm.* 2020;77(11):835–863.
doi:10.1093/ajhp/zxaa036

**Target as summarized by:** Murphy, Tang Girdwood, Scheetz. *J Hosp Med.* 2020;15(12):740–742.
doi:10.12788/jhm.3507

| Item | Value |
|---|---|
| Target (adults, serious MRSA) | AUC24/MIC 400–600 |
| MIC assumption | 1 mg/L → AUC24 400–600 mg·h/L |
| Trough-only monitoring | Replaced for serious MRSA infections |

**Note:** the 400–600 range is taken from the J Hosp Med summary, which quotes the guideline.
**UNVERIFIED** against the guideline's full text. See Open issue 3.

Note on era: Thomson's model was built when trough targets were used. The PK model itself
doesn't depend on the target, so we can grade against AUC.

---

## 3. Reference data for grader validation

From Thomson 2009, evaluation group (100 separate adults, Glasgow), using the paper's new
dosing guideline:

| Outcome | Reported value |
|---|---|
| Mean (SD) AUC24 | 520 (124) mg·h/L |
| Mean (SD) trough, days 1–4 | 12.2 (3.4) mg/L |
| AUC24/MIC > 400 | 87% of patients |

The paper's new maintenance table (CrCL band → dose, interval) is a second check:
our grader, applied to typical patients in each band, should land near AUC24 400–600.

| CrCL (mL/min) | Dose | Interval |
|---|---|---|
| <20 | 500 mg | 48 h |
| 20–29 | 500 mg | 24 h |
| 30–39 | 750 mg | 24 h |
| 40–54 | 500 mg | 12 h |
| 55–74 | 750 mg | 12 h |
| 75–89 | 1000 mg | 12 h |
| 90–110 | 1250 mg | 12 h |
| >110 | 1500 mg | 12 h |

Loading dose in the paper: <60 kg 1000 mg; 60–90 kg 1500 mg; >90 kg 2000 mg.

**This table is reference data for validation only. It is not dosing advice.**

---

## 4. Open issues (must close before tasks ship)

1. **Q unit.** Paper's Table 2 prints "h-1"; InsightRX treats Q as L/h. Physically, an
   inter-compartmental clearance is L/h. Plan: simulate both and keep the one that
   reproduces the paper's reported AUC24 and trough results (Section 3). Log the result in
   `VALIDATION.md`.
2. **Safety threshold.** The AUC level linked to kidney injury is not yet sourced.
   Spec's safety check stays disabled until it is.
3. **Guideline full text.** Confirm the 400–600 target and MIC assumption directly in Rybak 2020.
4. **Expert review.** None yet. All tasks marked `reviewed_by: pending`.
