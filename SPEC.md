# DoseSim Environment Spec — v0.1

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
| `get_labs(day)` | Labs up to `day` (never later than today), incl. resulted drug levels |
| `simulate(dose_mg, interval_h, days, loading_dose_mg?)` | Population-model what-if. Doesn't know the hidden patient |
| `submit_dose(day, dose_mg, interval_h, rationale, loading_dose_mg?)` | Locks in the regimen from that day on |

Agents may call `simulate` freely. Only `submit_dose` is graded. Definitions: `dosesim/tools.py`.

Schedule rules (v0): intervals 8, 12 or 24 h. A changed regimen's next dose = later of day start and
last dose + new interval (no hidden extra doses). Loading dose day 0 only, max 35 mg/kg and 3000 mg.

## 5. Grading (reward)
Reward is 0 to 1, built from parts so labs can see why a score was given:

| Part | Weight | Pass condition |
|---|---|---|
| In target range | 0.6 | Share of graded days with true-patient AUC24 inside `target_range` (day 0 not graded) |
| Safety | 0.3 | **OFF in v0** (no sourced toxicity threshold). Weights rescaled: range 0.857, rationale 0.143 |
| Rationale | 0.1 | Mentions each required idea (keyword groups). Crude; v0 only |

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
3. A correct answer exists: an oracle that knows the hidden patient scores a perfect range score.
4. A lazy answer fails: textbook regimen fixed on day 0 scores < 1 (not required for `easy` tasks).
5. Q-unit robust: oracle verdict identical under both Q readings; lazy answer fails under both.
6. Not copied or paraphrased from a public benchmark.
7. Expert review logged (sampled: 100% of first 50 tasks, then 10%). Reported, not blocking, until a reviewer exists.

Automated in `scripts/check_tasks.py`.

## 8. Grader validation (before any task ships)
- Reproduce the source paper's reported results. Report error.
- Check the source's own dosing table lands in the target range. Report mismatches.
- (Planned) Compare against the FDA label's renal dosing guidance.
- Publish results in `VALIDATION.md`. Failures block release.

## 9. Packaging
- Core: Docker image with grader, tools and task files. Wrapper-independent.
- Done: MCP tool server (`dosesim/mcp_server.py`), runner for Anthropic/OpenAI APIs (`scripts/run_model.py`).
- Next: `verifiers` (Prime Intellect) adapter. Buyer formats on request.
- Logs: every tool call, observation and reward saved per run.

## 10. Documentation
- `DATASHEET.md` (Datasheets for Datasets format): how tasks were made, who reviewed,
  AI assistance used, known limits, intended use.
- `CHANGELOG.md`: every version change.

## 11. Open questions
- Safety threshold for vancomycin (AUC linked to kidney injury): needs a primary source.
- Who is the expert reviewer?
- Rationale scoring: replace keywords with a rubric?
- Q unit in Thomson 2009 (L/h vs h-1): mitigated by gate 5, still unresolved.
