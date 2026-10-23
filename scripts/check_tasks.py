"""Quality gates for every task (SPEC.md section 7). A task ships only if all automatic gates pass.

Gates
  G1 fields + citations present
  G2 patient inside the grader model's validated range, every day
  G3 a correct answer exists   -> an "oracle" that knows the hidden patient reaches a perfect range score
  G4 a lazy answer fails       -> a "naive" fixed regimen scores < 1 (skipped for tasks marked easy)
  G5 Q-unit robustness         -> oracle verdicts identical under both Q readings; naive fails under both
  G6 not from a public benchmark (author attestation)
  G7 expert review             -> reported only; does not block in v0 (no reviewer yet)

Run: python3 -m scripts.check_tasks
Writes: tasks/vanc_check_report.json, tasks/vanc_solutions.json (private: never ship with the test split)
"""

import copy
import json
from pathlib import Path

from dosesim.env import DoseEnv
from dosesim.pk import cockcroft_gault, typical_params

TASK_DIR = Path(__file__).resolve().parent.parent / "tasks" / "vanc"
DOSES = [250 * k for k in range(2, 13)]          # 500 .. 3000 mg
INTERVALS = [8, 12, 24]
LOADS = [None, 1500, 2000, 2500, 3000]
REQUIRED = ["task_id", "version", "task_type", "split", "drug", "patient", "prompt",
            "tools_allowed", "success", "hidden", "grader", "provenance"]


def run_plan(task, plan, q_unit="L/h"):
    """plan = list of (dose, interval, loading, rationale) per day. Returns the grade."""
    env = DoseEnv(copy.deepcopy(task), q_unit=q_unit)
    for day, (dose, tau, load, why) in enumerate(plan):
        env.submit_dose(day, dose, tau, why, loading_dose_mg=load)
    return env.grade()


def oracle(task):
    """Knows the hidden patient. Picks each day's regimen greedily to keep AUC near 500."""
    n = len(task["patient"]["scr_by_day"])
    graded = set(task["success"]["graded_days"])
    plan = []
    for day in range(n):
        best = None
        cap = min(35 * task["patient"]["weight_kg"], 3000)
        for load in ([x for x in LOADS if x is None or x <= cap] if day == 0 else [None]):
            for dose in DOSES:
                for tau in INTERVALS:
                    # today's choice, then the same regimen (no loading) to the end
                    trial = plan + [(dose, tau, load, "")] + [(dose, tau, None, "")] * (n - day - 1)
                    g = run_plan(task, trial)
                    upto = [d for d in range(day + 2) if d < n]
                    hits = sum(g["in_range"][g["graded_days"].index(d)] for d in upto if d in graded)
                    miss = sum(abs(g["auc24_by_day"][d] - 500) for d in upto if d in graded)
                    changed = bool(plan) and (dose, tau) != plan[-1][:2]
                    # most days in range, then fewest changes, then closest to 500, then least drug
                    key = (-hits, changed, miss, dose * 24 / tau)
                    if best is None or key < best[0]:
                        best = (key, (dose, tau, load, ""))
        plan.append(best[1])
    why = " ".join(k[0] for k in task["success"].get("rationale_keywords", []))  # satisfies the rubric
    return [(d, t, l, why) for d, t, l, _ in plan]


def naive(task):
    """Lazy agent: textbook population model at day-0 kidney function, never adjusts.
    Picks the regimen whose population steady-state AUC24 is closest to 500; loading ~25 mg/kg."""
    p = task["patient"]
    crcl0 = cockcroft_gault(p["age_yr"], p["weight_kg"], p["scr_by_day"][0], p["sex"])
    cl = typical_params(p["weight_kg"], crcl0).CL
    dose, tau = min(((d, t) for d in DOSES for t in INTERVALS), key=lambda x: abs(x[0] * 24 / x[1] / cl - 500))
    load = min(3000, round(25 * p["weight_kg"] / 250) * 250)   # 25 mg/kg: inside the 20-35 mg/kg limit
    n = len(p["scr_by_day"])
    return [(dose, tau, load, "")] + [(dose, tau, None, "")] * (n - 1)


def check(task):
    res = {"task_id": task["task_id"], "gates": {}}
    # G1
    missing = [k for k in REQUIRED if k not in task]
    res["gates"]["G1_fields_and_citations"] = not missing and len(task["provenance"]["sources"]) > 0
    # G2
    p = task["patient"]
    lo_hi = task["grader"]["validated_ranges"]
    crcls = [cockcroft_gault(p["age_yr"], p["weight_kg"], s, p["sex"]) for s in p["scr_by_day"]]
    res["crcl_by_day"] = [round(c, 1) for c in crcls]
    res["gates"]["G2_in_validated_range"] = (
        lo_hi["age_yr"][0] <= p["age_yr"] <= lo_hi["age_yr"][1]
        and lo_hi["weight_kg"][0] <= p["weight_kg"] <= lo_hi["weight_kg"][1]
        and all(lo_hi["crcl_ml_min"][0] <= c <= lo_hi["crcl_ml_min"][1] for c in crcls))
    # G3
    o_plan = oracle(task)
    o = run_plan(task, o_plan)
    res["oracle"] = {"plan": [(d, t, l) for d, t, l, _ in o_plan], "auc24": o["auc24_by_day"],
                     "reward": o["reward"]}
    res["gates"]["G3_correct_answer_exists"] = o["range_score"] == 1.0
    # G4
    n_plan = naive(task)
    nv = run_plan(task, n_plan)
    res["naive"] = {"plan": [(d, t, l) for d, t, l, _ in n_plan], "auc24": nv["auc24_by_day"],
                    "range_score": nv["range_score"]}
    is_easy = task.get("difficulty") == "easy"
    res["gates"]["G4_lazy_answer_fails"] = True if is_easy else nv["range_score"] < 1.0
    # G5: the open Q-unit question must not change what the task tests.
    #   correct answer is correct under both readings; lazy answer fails under both (non-easy tasks)
    oracle_same = run_plan(task, o_plan, "L/h")["in_range"] == run_plan(task, o_plan, "h-1")["in_range"]
    naive_fails_both = is_easy or all(run_plan(task, n_plan, q)["range_score"] < 1.0 for q in ("L/h", "h-1"))
    res["gates"]["G5_q_unit_robust"] = oracle_same and naive_fails_both
    # G6, G7
    res["gates"]["G6_not_public_benchmark"] = bool(task["provenance"].get("not_from_public_benchmark"))
    res["expert_review"] = task["provenance"]["reviewed_by"]
    res["ships"] = all(res["gates"].values())
    return res


def main():
    reports, solutions = [], {}
    for path in sorted(TASK_DIR.glob("*.json")):
        task = json.loads(path.read_text())
        r = check(task)
        reports.append(r)
        solutions[task["task_id"]] = r["oracle"]["plan"]
        flags = " ".join(k.split("_")[0] for k, v in r["gates"].items() if not v) or "all pass"
        print(f"{r['task_id']}  ships={r['ships']}  naive_range={r['naive']['range_score']:.2f}  "
              f"oracle={r['oracle']['plan']}  failed: {flags}")
    out = TASK_DIR.parent
    (out / "vanc_check_report.json").write_text(json.dumps(reports, indent=2))
    (out / "vanc_solutions.json").write_text(json.dumps(solutions, indent=2))


if __name__ == "__main__":
    main()
