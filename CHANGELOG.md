# Changelog

## 0.1.0 — 2026-10-23
First working version.
- PK simulator for vancomycin (Thomson 2009), exact matrix-exponential solution. 7 math tests.
- Grader validated against the paper (`VALIDATION.md`): mean steady-state AUC24 within 2–4%.
- Environment: `get_labs`, `simulate`, `submit_dose`; hidden true patient; drawn levels with fixed lab error.
- 10 tasks; quality gates G1–G7 (`scripts/check_tasks.py`); all 10 pass.
- Model runner (Anthropic / OpenAI), MCP tool server, Dockerfile.

### Problems found by the gates and fixed before release
- Schedule loophole: changing regimen restarted the dose clock, so "q48h" could mean daily dosing. Fixed: next dose = later of day start and last dose + new interval.
- q48h made daily AUC see-saw; removed for v0 (no v0 patient needs it).
- Reward hack: oversized loading dose (3,000 mg for 45 kg). Fixed: cap 35 mg/kg, max 3,000 mg.
- Future-labs leak: `get_labs` accepted later days. Fixed and tested.
- Task 0005: lazy answer passed under one Q reading → hidden clearance strengthened. Patient moved off the edge of the validated CrCL range.
- Tasks 0004, 0008, 0009 relabeled easy (textbook calculation solves them).
