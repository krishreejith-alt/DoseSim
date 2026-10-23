# Task set v0.1 — vancomycin (10 tasks)

All tasks pass every automatic quality gate (`python3 -m scripts.check_tasks`). Expert review: pending.
Reference answers are private (`tasks/vanc_solutions.json`, git-ignored).

| Task | Scenario | Days | CrCL day 0 → last (mL/min) | Levels drawn | Lazy answer score* | Difficulty (hint) |
|---|---|---|---|---|---|---|
| 0001 | Stable, normal kidneys | 4 | 98 → 98 | 0 | 1.00 | easy |
| 0002 | Kidney function falling (contrast AKI) | 4 | 67 → 29 | 0 | 0.33 | medium |
| 0003 | Kidney function recovering | 4 | 42 → 92 | 0 | 0.33 | medium |
| 0004 | Frail 86F, low CrCL | 4 | 21 → 21 | 0 | 1.00 | easy |
| 0005 | Young, high clearance + hidden fast clearer | 4 | 157 → 157 | 1 | 0.00 | hard |
| 0006 | Hidden fast clearer, levels reveal it | 5 | 93 → 93 | 2 | 0.00 | hard |
| 0007 | Hidden slow clearer, levels reveal it | 5 | 66 → 66 | 2 | 0.50 | hard |
| 0008 | 140 kg patient | 4 | 173 → 173 | 0 | 1.00 | easy |
| 0009 | 45 kg patient | 4 | 46 → 46 | 0 | 1.00 | easy |
| 0010 | Falling kidneys + slow clearer + one level | 5 | 47 → 23 | 1 | 0.50 | hard |

*Lazy answer = textbook population-model regimen picked on day 0 and never changed. Share of graded days in range.

## What each type tests
- **easy:** correct basic calculation (Cockcroft-Gault, weight, interval choice). A careful textbook answer works.
- **medium:** noticing daily creatinine changes and re-dosing.
- **hard:** using measured drug levels to correct for a patient who handles the drug differently from average.

"Difficulty" is a design hint. Real difficulty gets set from model results (see `scripts/run_model.py`).

## Hidden information
Each patient has a hidden "true" drug handling (`hidden.eta`) and fixed lab errors on drawn levels.
The agent never sees these. It sees only labs, measured levels and the population what-if tool.
