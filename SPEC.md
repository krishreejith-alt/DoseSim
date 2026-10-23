# DoseSim Environment Spec — v0.1 (draft)

Status: draft for review. Owner: Shreejith. Last updated: 2026-10-23.

## 1. Purpose
RL environments where an AI agent makes clinical dosing decisions over time.
A validated pharmacokinetic (PK) model grades each decision. No human grading in the loop.

## 2. Scope (v0)
- In: adult IV dosing with renal (kidney) adjustment, multi-day, using published popPK models.
- Out (for now): pediatrics, oncology dose-finding, toxicity prediction, oral absorption.
  Reason: keep v0 inside well-validated models. Add later.
- Independence: DoseSim uses only published, externally validated PK models.
  It does not use RenalRisk or any in-house predictive model.

## 3. Task format
One JSON file per task. Every field is required unless marked optional.

```json
{
  "task_id": "dose-vanc-0001",          // unique, never reused
  "version": "0.1.0",                    // bump on any change
  "task_type": "renal_adjustment_multiday",
  "difficulty": "medium",                // easy | medium | hard (set after model runs)
  "split": "test",                       // train | test (test is never shown publicly)

  "drug": "vancomycin",
  "patient": {                           // inputs to the PK model
    "age_yr": null, "weight_kg": null, "sex": null,
    "scr_by_day": []                     // serum creatinine per day
  },
  "timeline": [],                        // events revealed each day (labs, notes)
  "prompt": "",                          // written as a clinical consult, see Section 6

  "tools_allowed": ["get_labs", "simulate", "submit_dose"],

  "success": {                           // what counts as correct
    "metric": "",                        // e.g. AUC or trough
    "target_range": [null, null],
    "target_source": ""                  // citation for the target range
  },

  "grader": {
    "model_id": "",                      // which popPK model
    "model_source": "",                  // DOI of the paper
    "validated_ranges": {},              // patient ranges the model was built on
    "in_range_check": true               // task must sit inside validated ranges
  },

  "provenance": {
    "sources": [],                       // every fact used, with citation
    "authored_by": "",                   // human | ai_assisted (always disclosed)
    "reviewed_by": "",                   // expert reviewer, or "pending"
    "review_date": null
  }
}
```

## 4. Tools (MCP interface)
| Tool | What it does |
|---|---|
| `get_labs(day)` | Returns that day's lab values from the timeline |
| `simulate(dose_mg, interval_h, days)` | Runs the PK model, returns predicted drug levels |
| `submit_dose(day, dose_mg, interval_h, rationale)` | Locks in the decision for that day |

Agents may call `simulate` freely. Only `submit_dose` is graded.

## 5. Grading (reward)
Reward is 0 to 1, built from parts so labs can see why a score was given:

| Part | Weight | Pass condition |
|---|---|---|
| In target range | 0.6 | Simulated exposure inside `target_range` on every graded day |
| Safety | 0.3 | No day above the toxicity threshold (hard fail = total reward 0) |
| Rationale | 0.1 | Mentions the key driver (e.g. kidney function change). Rubric-checked |

Rules:
- Grader is deterministic: same inputs, same score.
- Grading uses ranges, not exact doses. Several doses can be correct.
- Any task outside the model's validated ranges is rejected before release.

## 6. Writing standard
- Write prompts like real consult requests: short, clinical, some irrelevant details, normal units.
- Vary structure and wording across tasks. No templates that repeat word for word.
- No generic AI phrasing. No perfectly round numbers unless realistic.
- Writing style is about realism only. Provenance is always disclosed (Section 3).

## 7. Quality gates (a task ships only if all pass)
1. Every fact has a citation in `provenance.sources`.
2. Patient sits inside the grader model's validated ranges.
3. At least one correct answer exists and the grader accepts it.
4. A known wrong answer exists and the grader rejects it.
5. Not copied or paraphrased from a public benchmark.
6. Expert review logged (sampled: 100% of first 50 tasks, then 10%).

## 8. Grader validation (before any task ships)
- Reproduce observed drug levels from the source paper. Report error.
- Reproduce the FDA label's renal dose table direction and size. Report mismatches.
- Publish results in `VALIDATION.md`. Failures block release.

## 9. Packaging
- Core: Docker image with grader, tools and task files. Wrapper-independent.
- Adapters: `verifiers` (Prime Intellect) first. Buyer formats on request.
- Logs: every tool call, observation and reward saved per run.

## 10. Documentation
- `DATASHEET.md` (Datasheets for Datasets format): how tasks were made, who reviewed,
  AI assistance used, known limits, intended use.
- `CHANGELOG.md`: every version change.

## 11. Open questions
- Which target metric per drug (AUC vs trough)? Decide per drug from guidelines.
- Who is the expert reviewer?
- Rationale scoring: rubric by model or by keyword check?
