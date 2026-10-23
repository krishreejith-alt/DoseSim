# DoseSim

RL environments for clinical dosing decisions.
An AI agent doses a patient day by day. A published, validated PK model grades each choice. No human graders.

## Status: v0.1
- 1 drug (vancomycin), 10 tasks, all passing every quality gate.
- Grader validated against its source paper (`VALIDATION.md`).
- No expert review yet. Not clinical advice.

## Quick start
```bash
pip install -r requirements.txt
python3 -m pytest -q tests          # 25 tests
python3 -m scripts.check_tasks      # quality gates on all tasks
python3 -m scripts.run_model --provider anthropic --model <model-id> --repeats 3   # needs an API key
```

## What's where
| File | What it is |
|---|---|
| `SPEC.md` | Task format, tools, grading, quality gates. Start here |
| `sources/vancomycin.md` | Every number and its source |
| `VALIDATION.md` | Does the grader match the paper? |
| `TASKS.md` | The 10 tasks at a glance |
| `DATASHEET.md` | How tasks were made, limits, intended use |
| `dosesim/pk.py` | PK simulator (the grader core) |
| `dosesim/env.py` | Environment: tools, hidden patient, grading |
| `dosesim/mcp_server.py` | MCP tool server for agent harnesses |
| `scripts/check_tasks.py` | Quality gates |
| `scripts/run_model.py` | Run a model on the tasks |

## Principles
- Every fact cites a primary source (or is marked UNVERIFIED).
- Grader uses only published, externally validated models, inside their validated patient ranges.
- How each task was made (human or AI-assisted, who reviewed it) is always recorded.
