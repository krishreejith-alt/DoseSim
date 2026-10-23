# Datasheet — DoseSim vancomycin task set v0.1

Format follows "Datasheets for Datasets" (Gebru et al., Commun ACM 2021).

## Motivation
- **Purpose:** train and evaluate AI agents on multi-day clinical dosing decisions, scored automatically by a
  published pharmacokinetic model instead of human graders.
- **Created by:** Shreejith (DoseSim). AI assistant used for drafting code, scenarios and prompts (see Composition).
- **Funding:** none.

## Composition
- 10 tasks, one patient each, 4–5 days. Adults only. IV vancomycin. AUC24 target 400–600 mg·h/L.
- Each task: prompt (consult-note style), patient data, hidden patient effects, grading settings, provenance.
- **All patients are synthetic.** No real patient data. No personal information.
- **Authorship:** every scenario and prompt was drafted with an AI assistant (`authored_by: ai_assisted`).
  Founder check: pending. Expert review: none yet.
- **Not copied** from any public benchmark.
- **Split:** all 10 are `test`. Do not train on them.

## How the grader works and where its numbers come from
- Model: Thomson et al., J Antimicrob Chemother 2009 (doi:10.1093/jac/dkp085). Built from 398 adults.
- Target: Rybak et al., Am J Health Syst Pharm 2020 (doi:10.1093/ajhp/zxaa036).
- Full sourcing: `sources/vancomycin.md`. Validation results: `VALIDATION.md`.

## Collection / generation process
1. Scenarios written by hand (AI-assisted) to cover distinct dosing problems.
2. Hidden effects and lab errors drawn with a fixed seed (`tasks/build_tasks.py`, seed 7031). Rebuild = identical files.
3. Every task passes automatic gates: citations present, inside validated patient ranges, a correct answer exists,
   a lazy answer fails (except easy tasks), verdict unchanged by the open Q-unit question.

## Known limits (read before use)
- **Model limits:** retrospective UK data; no dialysis patients; care advised in obese/underweight patients.
- **Variability:** our virtual patients vary more than the paper's reported predictions (likely shrinkage; see VALIDATION.md).
- **Safety scoring is off:** no sourced kidney-injury threshold yet. Overexposure is only penalized by the AUC ceiling (600).
- **Rationale scoring is crude:** keyword check, 10% of reward. Can be gamed by keyword stuffing.
- **Loading-dose limit** (35 mg/kg, max 3000 mg) comes from a secondary summary of the 2020 guideline. Full text not yet checked.
- **Infusion rate** assumed at 1 g/h (tested: negligible effect on AUC).
- **Not clinical advice.** Tasks and reference answers are for AI evaluation only.

## Uses
- **Good for:** measuring whether agents adjust doses to changing kidney function and to measured levels.
- **Not for:** dosing real patients, pediatric or dialysis dosing, or claims about clinical safety.

## Maintenance
- Versioned (`version` in every task; `CHANGELOG.md`). Issues found → new version, never silent edits.
