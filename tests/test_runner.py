"""Runner checks with scripted (fake) agents, so no API key is needed."""

import json
from pathlib import Path

from dosesim.runner import run_episode

TASKS = Path(__file__).resolve().parent.parent / "tasks" / "vanc"


class ScriptedAgent:
    """Each turn: read labs, then submit a fixed regimen. Mimics a real tool-calling agent."""

    def __init__(self, dose, tau):
        self.dose, self.tau, self.n = dose, tau, 0

    def respond(self, messages, tools):
        last = messages[-1]
        day = int(last["content"].split()[1].rstrip(",")) if last["role"] == "user" and last["content"].startswith("Day") else None
        self.n += 1
        if day is not None:
            self.day = day
            return {"text": "", "tool_calls": [{"id": f"c{self.n}", "name": "get_labs", "args": {"day": day}}]}
        if last["role"] == "tool" and last["name"] == "get_labs":
            return {"text": "", "tool_calls": [{"id": f"c{self.n}", "name": "submit_dose", "args": {
                "day": self.day, "dose_mg": self.dose, "interval_h": self.tau,
                "rationale": "dosed on creatinine clearance and weight"}}]}
        return {"text": "done", "tool_calls": []}


class SilentAgent:
    def respond(self, messages, tools):
        return {"text": "I'm not sure.", "tool_calls": []}


def task(tid):
    return json.loads((TASKS / f"dose-vanc-{tid}.json").read_text())


def test_scripted_agent_finishes_and_is_graded():
    r = run_episode(task("0001"), ScriptedAgent(1250, 12))
    assert r["finished"] and 0 <= r["grade"]["reward"] <= 1
    assert any(t["tool"] == "submit_dose" for t in r["transcript"])


def test_agent_that_never_submits_scores_zero():
    r = run_episode(task("0001"), SilentAgent())
    assert not r["finished"] and r["grade"]["reward"] == 0.0


def test_prompt_never_contains_hidden_fields():
    t = task("0006")
    assert "eta" not in t["prompt"] and "hidden" not in t["prompt"]
