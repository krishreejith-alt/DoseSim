# DoseSim

RL environments for clinical dosing decisions.
An AI agent picks drug doses over time. A published, validated PK model grades each choice.

## Status
v0.1 — spec only. No tasks or grader yet.

## Files
- `SPEC.md` — task format, tools, grading, quality gates. Start here.

## Principles
- Every fact cites a primary source (FDA label, peer-reviewed popPK paper).
- Grader uses only published, externally validated models, inside their validated patient ranges.
- How each task was made (human or AI-assisted, who reviewed it) is always recorded.
