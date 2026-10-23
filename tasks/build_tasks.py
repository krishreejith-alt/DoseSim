"""Builds the v0 vancomycin task files (tasks/vanc/*.json) from the scenarios below.

Scenarios and prompts are written by hand (AI-assisted, disclosed in each task's provenance).
Random parts (hidden patient effects, lab error) use a fixed seed, so rebuilding gives identical files.

Run: python3 -m tasks.build_tasks
"""

import json
from pathlib import Path

import numpy as np

from dosesim.pk import IIV_CV

OUT = Path(__file__).parent / "vanc"
SEED = 7031

SOURCES = [
    {"fact": "PK model, parameters, validated covariate ranges",
     "cite": "Thomson AH et al. J Antimicrob Chemother. 2009;63(5):1050-1057. doi:10.1093/jac/dkp085"},
    {"fact": "AUC24/MIC target 400-600, MIC 1 mg/L assumed",
     "cite": "Rybak MJ et al. Am J Health Syst Pharm. 2020;77(11):835-863. doi:10.1093/ajhp/zxaa036"},
    {"fact": "Creatinine clearance equation (total body weight)",
     "cite": "Cockcroft DW, Gault MH. Nephron. 1976;16(1):31-41"},
    {"fact": "Loading dose limit 20-35 mg/kg, max 3000 mg (secondary summary; full text UNVERIFIED)",
     "cite": "DoseMeRx summary of Rybak 2020: doseme-rx.com/vancomycin/articles/dosing-guidelines-essentials"},
    {"fact": "Lab error size for drawn levels (additive 1.6 mg/L, proportional 15%)",
     "cite": "Thomson 2009, Table 2 residual error"},
]

COMMON = (
    "\n\nYou are the pharmacist dosing vancomycin for this patient. Target: AUC24 400-600 mg*h/L "
    "(MIC assumed 1 mg/L), per our institutional AUC protocol. Each day you get that morning's labs, "
    "then you set the regimen that starts that day. Use the tools: get_labs, simulate, submit_dose. "
    "Allowed intervals: 8, 12 or 24 h. A loading dose is allowed on day 0 only."
)

# eta_sd: hidden patient's clearance, in units of between-patient SD (0 = textbook patient).
# draws: hours when a vancomycin level is drawn (visible from the next decision onward).
SCENARIOS = [
    dict(id="0001", type="stable_baseline", diff_hint="easy",
         age=54, sex="M", wt=82, scr=[1.0, 1.0, 1.0, 1.0], eta_sd=0.0, draws=[],
         keywords=[["creatinine", "crcl", "renal", "kidney", "clearance"]],
         prompt=("54M admitted from the ED with MRSA bacteremia, likely source an infected PICC line "
                 "(line out yesterday). Hemodynamically stable. ID has asked for vancomycin. Allergies: none. "
                 "No nephrotoxins on board.")),
    dict(id="0002", type="renal_decline", diff_hint="medium",
         age=68, sex="F", wt=71, scr=[0.9, 1.3, 1.8, 2.1], eta_sd=0.0, draws=[],
         keywords=[["creatinine", "crcl", "renal", "kidney", "aki"], ["reduc", "lower", "decreas", "extend"]],
         prompt=("68F, MRSA pneumonia, transferred to step-down overnight. Got IV contrast for a CT "
                 "angiogram the day before admission, and the team is worried about her kidneys. "
                 "Urine output has been soft. Please manage vancomycin.")),
    dict(id="0003", type="renal_recovery", diff_hint="medium",
         age=59, sex="M", wt=90, scr=[2.4, 1.9, 1.4, 1.1], eta_sd=0.0, draws=[],
         keywords=[["creatinine", "crcl", "renal", "kidney"], ["increas", "raise", "higher", "shorten"]],
         prompt=("59M with MRSA septic arthritis of the knee, washed out in OR yesterday. Came in "
                 "dehydrated with a prerenal AKI, now on fluids. Nephrology thinks the kidneys will "
                 "recover. Vancomycin per pharmacy.")),
    dict(id="0004", type="low_crcl_elderly", diff_hint="easy",
         age=86, sex="F", wt=52, scr=[1.6, 1.6, 1.7, 1.6], eta_sd=0.0, draws=[],
         keywords=[["creatinine", "crcl", "renal", "kidney", "clearance"], ["interval", "q24", "every 24", "once daily", "extend"]],
         prompt=("86F nursing-home resident, MRSA from a sacral wound with cellulitis and suspected "
                 "osteomyelitis. Frail, poor oral intake. Baseline CKD stage 3-4 per outside records. "
                 "Vancomycin, please dose.")),
    dict(id="0005", type="high_clearance", diff_hint="hard",
         age=24, sex="M", wt=78, scr=[0.8, 0.8, 0.8, 0.8], eta_sd=1.2, draws=[(23.5, "trough before day-1 dose")],
         keywords=[["creatinine", "crcl", "renal", "kidney", "clearance", "augmented"], ["level", "trough", "concentration"]],
         prompt=("24M, MRSA endocarditis (tricuspid), history of IV drug use. Young, good kidney "
                 "function, febrile. Surgery consulted but not operating yet. Pharmacy to dose vancomycin; "
                 "a level will be drawn before tomorrow morning's dose.")),
    dict(id="0006", type="hidden_fast_clearer", diff_hint="hard",
         age=47, sex="F", wt=68, scr=[0.8, 0.8, 0.8, 0.8, 0.8], eta_sd=1.4,
         draws=[(23.5, "trough before day-1 dose"), (47.5, "trough before day-2 dose")],
         keywords=[["level", "trough", "concentration", "measured"], ["increas", "raise", "higher", "underexpos", "low"]],
         prompt=("47F with MRSA bacteremia from an infected tunneled catheter placed for chemo "
                 "(catheter removed). Breast cancer on active treatment, otherwise well. "
                 "Kidney function normal. Levels will be drawn before the morning doses on days 1 and 2.")),
    dict(id="0007", type="hidden_slow_clearer", diff_hint="hard",
         age=72, sex="M", wt=77, scr=[1.1, 1.1, 1.1, 1.1, 1.1], eta_sd=-1.4,
         draws=[(23.5, "trough before day-1 dose"), (47.5, "trough before day-2 dose")],
         keywords=[["level", "trough", "concentration", "measured"], ["reduc", "lower", "decreas", "hold", "extend"]],
         prompt=("72M, MRSA vertebral osteomyelitis with a small epidural abscess, managed medically for now. "
                 "Diabetic, hypertensive. Creatinine has been stable at baseline. Morning troughs are ordered "
                 "for days 1 and 2.")),
    dict(id="0008", type="heavy_patient", diff_hint="easy",
         age=51, sex="M", wt=140, scr=[1.0, 1.0, 1.0, 1.0], eta_sd=0.0, draws=[],
         keywords=[["weight", "kg", "obes", "body"]],
         prompt=("51M, 140 kg, MRSA necrotizing soft-tissue infection of the thigh, post debridement. "
                 "On the floor after one night in the SICU. Kidney function at baseline. Please dose vanc.")),
    dict(id="0009", type="light_patient", diff_hint="easy",
         age=63, sex="F", wt=45, scr=[0.9, 0.9, 0.9, 0.9], eta_sd=0.0, draws=[],
         keywords=[["weight", "kg", "small", "low body"]],
         prompt=("63F, 45 kg, COPD, admitted with MRSA pneumonia after influenza. Thin, chronically ill. "
                 "Creatinine looks normal but the team notes she has very little muscle mass. Vanc per pharmacy.")),
    dict(id="0010", type="decline_plus_level", diff_hint="hard",
         age=77, sex="F", wt=63, scr=[1.0, 1.4, 1.8, 2.0, 2.0], eta_sd=-0.6,
         draws=[(47.5, "trough before day-2 dose")],
         keywords=[["creatinine", "crcl", "renal", "kidney", "aki"], ["level", "trough", "concentration"],
                   ["reduc", "lower", "decreas", "hold", "extend"]],
         prompt=("77F, MRSA bacteremia, source unclear (TTE negative, TEE pending). Started on "
                 "piperacillin-tazobactam empirically before cultures came back, now stopped. Creatinine "
                 "trending up since admission. A trough is ordered before the day-2 morning dose.")),
]


def omega(cv):
    return float(np.sqrt(np.log(1 + cv ** 2)))


def build():
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SCENARIOS:
        n = len(s["scr"])
        # Hidden patient: clearance shifted by eta_sd SDs; central volume gets a small random shift.
        eta = {"CL": s["eta_sd"] * omega(IIV_CV["CL"]),
               "V1": float(rng.normal(0, omega(IIV_CV["V1"])) * 0.5)}
        draws = [{"time_h": t, "label": lab,
                  "prop_error": float(np.clip(rng.normal(0, 0.15), -0.15, 0.15)),
                  "add_error": float(np.clip(rng.normal(0, 1.6), -1.6, 1.6))} for t, lab in s["draws"]]
        task = {
            "task_id": f"dose-vanc-{s['id']}",
            "version": "0.1.0",
            "task_type": s["type"],
            "difficulty": s["diff_hint"],     # hint now; replaced by measured difficulty after model runs
            "split": "test",
            "drug": "vancomycin",
            "patient": {"age_yr": s["age"], "sex": s["sex"], "weight_kg": s["wt"], "scr_by_day": s["scr"]},
            "prompt": s["prompt"] + COMMON + f" This episode runs {n} days (day 0 to day {n - 1}).",
            "tools_allowed": ["get_labs", "simulate", "submit_dose"],
            "success": {
                "metric": "AUC24 (true patient, simulated)",
                "target_range": [400, 600],
                "target_source": "Rybak 2020 (see provenance)",
                "graded_days": list(range(1, n)),   # day 0 excluded: loading phase
                "rationale_keywords": s["keywords"],
            },
            "hidden": {"eta": eta, "level_draws": draws},
            "grader": {
                "model_id": "thomson2009_vanco_2cmt",
                "model_source": "doi:10.1093/jac/dkp085",
                "validated_ranges": {"age_yr": [16, 97], "weight_kg": [40, 159], "crcl_ml_min": [12, 216]},
                "q_unit": "L/h (verdict must match under h-1; see VALIDATION.md)",
            },
            "provenance": {
                "sources": SOURCES,
                "authored_by": "ai_assisted",
                "author_note": "Scenario and prompt drafted with an AI assistant. Founder check: pending.",
                "not_from_public_benchmark": True,
                "reviewed_by": "pending",
                "review_date": None,
            },
        }
        (OUT / f"{task['task_id']}.json").write_text(json.dumps(task, indent=2))
    print(f"wrote {len(SCENARIOS)} tasks to {OUT}")


if __name__ == "__main__":
    build()
