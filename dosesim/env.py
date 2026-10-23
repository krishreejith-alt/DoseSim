"""DoseSim environment: one task = one patient, dosed day by day.

How an episode works
1. Each day the agent can read labs (get_labs), test ideas (simulate), then lock in a regimen (submit_dose).
2. The patient is a HIDDEN "true" patient: the published model plus fixed random effects,
   so the population model is not exactly right for them. Drug levels (when drawn) reveal it.
3. After the last day, the true patient is simulated with the agent's doses and graded.

Everything is deterministic: same task + same actions = same score.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .pk import Dose, cockcroft_gault, simulate, typical_params

ALLOWED_INTERVALS = (8, 12, 24)  # v0: no q48h (daily AUC see-saws; no v0 task needs it)
INFUSION_MG_PER_H = 1000.0  # assumption, see VALIDATION.md (barely affects AUC)

# v0 reward weights. Safety part (0.3) is OFF until a kidney-injury threshold is sourced,
# so the remaining weights are rescaled to sum to 1. See SPEC.md section 5.
W_RANGE, W_RATIONALE = 0.6, 0.1
W_TOTAL = W_RANGE + W_RATIONALE


@dataclass
class Submitted:
    day: int
    dose_mg: float
    interval_h: float
    loading_dose_mg: float | None
    rationale: str


@dataclass
class DoseEnv:
    task: dict
    q_unit: str = "L/h"
    submissions: dict = field(default_factory=dict)  # day -> Submitted
    log: list = field(default_factory=list)          # every call, for trace data
    done: bool = False

    # ---------- helpers ----------
    @classmethod
    def from_file(cls, path: str | Path, **kw) -> "DoseEnv":
        return cls(json.loads(Path(path).read_text()), **kw)

    @property
    def n_days(self) -> int:
        return len(self.task["patient"]["scr_by_day"])

    def _crcl_by_day(self) -> list[float]:
        p = self.task["patient"]
        return [cockcroft_gault(p["age_yr"], p["weight_kg"], s, p["sex"]) for s in p["scr_by_day"]]

    def _doses(self, upto_h: float | None = None) -> list[Dose]:
        """Turn the agent's daily decisions into dose times.

        Rules (like a real dosing schedule):
        - Day 0: first dose at hour 0 (the loading dose, if given), then every interval_h.
        - Same regimen as yesterday: the schedule just continues.
        - New regimen on day d: next dose = later of (start of day d) and (last dose + new interval).
          So a change can't sneak in extra doses by restarting the clock.
        - Each day's decision controls the doses due during that day [24d, 24d+24).
        """
        out: list[Dose] = []
        last_dose_h, next_due, prev = None, 0.0, None
        for d in sorted(self.submissions):
            s = self.submissions[d]
            regimen = (s.dose_mg, s.interval_h)
            day_start, day_end = 24.0 * d, 24.0 * (d + 1)
            if prev is not None and regimen != prev:
                next_due = max(day_start, last_dose_h + s.interval_h)
            while next_due < day_end - 1e-9:
                amt = s.loading_dose_mg if (not out and s.loading_dose_mg) else s.dose_mg
                out.append(Dose(next_due, amt, amt / INFUSION_MG_PER_H))
                last_dose_h, next_due = next_due, next_due + s.interval_h
            prev = regimen
        if upto_h is not None:
            out = [x for x in out if x.time_h < upto_h]
        return out

    def _true_sim(self, horizon_h: float, q_unit: str | None = None):
        p = self.task["patient"]
        return simulate(self._doses(), p["weight_kg"], self._crcl_by_day(), horizon_h,
                        q_unit=q_unit or self.q_unit, eta=self.task["hidden"]["eta"], dt=0.25)

    def _record(self, tool, args, result):
        self.log.append({"tool": tool, "args": args, "result": result})
        return result

    # ---------- tools the agent can call ----------
    def get_labs(self, day: int) -> dict:
        """Labs available up to and including `day`. Never shows the future:
        `day` can't be later than today's decision day (= number of days already submitted)."""
        today = min(len(self.submissions), self.n_days - 1)
        if not 0 <= day <= today:
            return self._record("get_labs", {"day": day}, {"error": f"labs only available up to day {today}"})
        p = self.task["patient"]
        labs = {
            "age_yr": p["age_yr"], "sex": p["sex"], "weight_kg": p["weight_kg"],
            "scr_mg_dl_by_day": p["scr_by_day"][: day + 1],
            "vancomycin_levels": [],
        }
        # Drug levels: drawn at fixed clock times; value comes from the TRUE patient
        # given the doses the agent actually gave, plus a fixed lab error from the task.
        for draw in self.task["hidden"].get("level_draws", []):
            # A level is visible on day d only if it was drawn before that day's decision (hour 24*d).
            if draw["time_h"] <= 24.0 * day and self.submissions:
                sim = self._true_sim(draw["time_h"] + 0.01)
                c = sim.conc_at(draw["time_h"]) * (1 + draw["prop_error"]) + draw["add_error"]
                labs["vancomycin_levels"].append(
                    {"time_h": draw["time_h"], "label": draw["label"], "mg_per_l": round(max(c, 0.0), 1)})
        return self._record("get_labs", {"day": day}, labs)

    def simulate(self, dose_mg: float, interval_h: float, days: int = 3,
                 loading_dose_mg: float | None = None) -> dict:
        """What-if tool. Uses the POPULATION model and the latest kidney function only.
        It does not know the hidden patient. Returns predicted AUC24 per day and trough."""
        p = self.task["patient"]
        latest = min(len(self.submissions), self.n_days - 1)  # today's decision day
        crcl = self._crcl_by_day()[latest]
        horizon = 24.0 * days
        doses, t, first = [], 0.0, True
        while t < horizon - 1e-9:
            amt = loading_dose_mg if (first and loading_dose_mg) else dose_mg
            doses.append(Dose(t, amt, amt / INFUSION_MG_PER_H))
            t += interval_h
            first = False
        r = simulate(doses, p["weight_kg"], [crcl], horizon, q_unit=self.q_unit, dt=0.25)
        out = {"assumed_crcl_ml_min": round(crcl, 1),
               "auc24_by_day": [round(a, 1) for a in r.auc24_by_day(days)],
               "last_trough_mg_per_l": round(r.troughs()[-1], 1) if len(doses) > 1 else None}
        return self._record("simulate", {"dose_mg": dose_mg, "interval_h": interval_h,
                                         "days": days, "loading_dose_mg": loading_dose_mg}, out)

    def submit_dose(self, day: int, dose_mg: float, interval_h: float, rationale: str = "",
                    loading_dose_mg: float | None = None) -> dict:
        """Lock in the regimen from `day` onward. One submission per day, in order."""
        expected = len(self.submissions)
        if self.done or day != expected:
            return self._record("submit_dose", {"day": day}, {"error": f"expected day {expected}"})
        if dose_mg <= 0 or interval_h not in ALLOWED_INTERVALS:
            return self._record("submit_dose", {"day": day}, {"error": "invalid dose or interval"})
        if loading_dose_mg is not None and day != 0:
            return self._record("submit_dose", {"day": day}, {"error": "loading dose only on day 0"})
        # Loading dose limit: 35 mg/kg actual body weight, max 3000 mg (2020 guideline as summarized;
        # see sources/vancomycin.md). Blocks the "giant loading dose" reward hack.
        if loading_dose_mg is not None:
            cap = min(35.0 * self.task["patient"]["weight_kg"], 3000.0)
            if not 0 < loading_dose_mg <= cap:
                return self._record("submit_dose", {"day": day},
                                    {"error": f"loading dose must be > 0 and <= {cap:.0f} mg"})
        self.submissions[day] = Submitted(day, dose_mg, interval_h, loading_dose_mg, rationale)
        if len(self.submissions) == self.n_days:
            self.done = True
        return self._record("submit_dose", {"day": day, "dose_mg": dose_mg, "interval_h": interval_h,
                                            "loading_dose_mg": loading_dose_mg}, {"ok": True, "done": self.done})

    # ---------- grading ----------
    def grade(self, q_unit: str | None = None) -> dict:
        """Reward 0-1. In-range share of graded days (0.6) + rationale check (0.1), rescaled."""
        if not self.done:
            return {"reward": 0.0, "reason": "episode not finished"}
        lo, hi = self.task["success"]["target_range"]
        sim = self._true_sim(24.0 * self.n_days, q_unit)
        aucs = sim.auc24_by_day(self.n_days)
        graded = self.task["success"]["graded_days"]
        in_range = [lo <= aucs[d] <= hi for d in graded]
        range_score = sum(in_range) / len(graded)

        # Rationale: must mention each required idea (any synonym counts). Crude by design; v0 only.
        text = " ".join(s.rationale.lower() for s in self.submissions.values())
        groups = self.task["success"].get("rationale_keywords", [])
        rat_score = (sum(any(k in text for k in g) for g in groups) / len(groups)) if groups else 1.0

        reward = (W_RANGE * range_score + W_RATIONALE * rat_score) / W_TOTAL
        return {"reward": round(reward, 4), "range_score": range_score, "rationale_score": rat_score,
                "auc24_by_day": [round(a, 1) for a in aucs], "graded_days": graded,
                "in_range": in_range, "q_unit": q_unit or self.q_unit}
