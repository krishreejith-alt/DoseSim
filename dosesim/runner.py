"""Runs an AI agent through a DoseSim task, day by day, and grades it.

The agent only ever sees: the task prompt, a daily "it's day N" message, and tool results.
Each agent is an object with one method:
    respond(messages, tools) -> {"text": str, "tool_calls": [{"id", "name", "args"}]}
Adapters for real APIs live in scripts/run_model.py.
"""

from __future__ import annotations

import copy
import json

from .env import DoseEnv
from .tools import TOOLS, call_tool

MAX_STEPS_PER_DAY = 10  # tool calls allowed per day before we move on


def run_episode(task: dict, agent, q_unit: str = "L/h") -> dict:
    env = DoseEnv(copy.deepcopy(task), q_unit=q_unit)
    messages = [{"role": "user", "content": task["prompt"]}]
    transcript = []
    for day in range(env.n_days):
        messages.append({"role": "user", "content": (
            f"Day {day}, morning. Today's labs are available (get_labs with day={day}). "
            f"Submit today's regimen with submit_dose(day={day}, ...).")})
        reminded = False
        for _ in range(MAX_STEPS_PER_DAY):
            out = agent.respond(messages, TOOLS)
            messages.append({"role": "assistant", "content": out.get("text", ""),
                             "tool_calls": out.get("tool_calls", [])})
            if not out.get("tool_calls"):
                if day in env.submissions or reminded:
                    break
                messages.append({"role": "user", "content": f"Please submit the day {day} regimen."})
                reminded = True
                continue
            for call in out["tool_calls"]:
                result = call_tool(env, call["name"], call.get("args", {}))
                transcript.append({"day": day, "tool": call["name"], "args": call.get("args", {}), "result": result})
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "name": call["name"],
                                 "content": json.dumps(result)})
            if day in env.submissions:
                break
        if day not in env.submissions:
            break  # agent never submitted: episode ends unfinished (scores 0)
    grade = env.grade()
    return {"task_id": task["task_id"], "grade": grade, "transcript": transcript,
            "finished": env.done}
