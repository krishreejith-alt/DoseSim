"""Run a real model on the DoseSim tasks and save scores + full traces.

Usage:
  export ANTHROPIC_API_KEY=...   (or OPENAI_API_KEY=...)
  python3 -m scripts.run_model --provider anthropic --model <model-id> --repeats 3
  python3 -m scripts.run_model --provider openai --model <model-id> --repeats 3

Writes: runs/<provider>_<model>_<timestamp>.jsonl (one line per episode) and prints a summary.
Model IDs change often; use whatever your provider lists. Nothing here is tuned to one model.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from dosesim.runner import run_episode

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = "You are a clinical pharmacist. Use the tools provided. Be concise."


# ---------- message format converters (pure functions, unit-tested) ----------
def to_anthropic(messages: list[dict]) -> list[dict]:
    """Internal messages -> Anthropic Messages API format (roles must alternate)."""
    out: list[dict] = []

    def add(role, blocks):
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})

    for m in messages:
        if m["role"] == "user":
            add("user", [{"type": "text", "text": m["content"]}])
        elif m["role"] == "assistant":
            blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c.get("args", {})}
                       for c in m.get("tool_calls", [])]
            add("assistant", blocks or [{"type": "text", "text": "(no reply)"}])
        elif m["role"] == "tool":
            add("user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}])
    # tool_result blocks must come before text in a user turn
    for turn in out:
        if turn["role"] == "user":
            turn["content"].sort(key=lambda b: b["type"] != "tool_result")
    return out


def to_openai(messages: list[dict]) -> list[dict]:
    """Internal messages -> OpenAI Chat Completions format."""
    out = [{"role": "system", "content": SYSTEM}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                      "function": {"name": c["name"], "arguments": json.dumps(c.get("args", {}))}}
                                     for c in m["tool_calls"]]
            out.append(msg)
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
    return out


# ---------- agents ----------
class AnthropicAgent:
    def __init__(self, model):
        import anthropic
        self.client, self.model = anthropic.Anthropic(), model

    def respond(self, messages, tools):
        r = self.client.messages.create(
            model=self.model, max_tokens=2048, system=SYSTEM, messages=to_anthropic(messages),
            tools=[{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                   for t in tools])
        text = "".join(b.text for b in r.content if b.type == "text")
        calls = [{"id": b.id, "name": b.name, "args": b.input} for b in r.content if b.type == "tool_use"]
        return {"text": text, "tool_calls": calls}


class OpenAIAgent:
    def __init__(self, model):
        import openai
        self.client, self.model = openai.OpenAI(), model

    def respond(self, messages, tools):
        r = self.client.chat.completions.create(
            model=self.model, messages=to_openai(messages),
            tools=[{"type": "function", "function": t} for t in tools])
        m = r.choices[0].message
        calls = [{"id": c.id, "name": c.function.name, "args": json.loads(c.function.arguments or "{}")}
                 for c in (m.tool_calls or [])]
        return {"text": m.content or "", "tool_calls": calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--repeats", type=int, default=1, help="runs per task (models are random; use 3+)")
    ap.add_argument("--tasks", default=str(ROOT / "tasks" / "vanc"))
    a = ap.parse_args()

    key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}[a.provider]
    if not os.environ.get(key):
        raise SystemExit(f"Set {key} first.")
    agent = (AnthropicAgent if a.provider == "anthropic" else OpenAIAgent)(a.model)

    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{a.provider}_{a.model.replace('/', '_')}_{int(time.time())}.jsonl"
    by_task: dict[str, list[float]] = {}
    with out.open("w") as f:
        for path in sorted(Path(a.tasks).glob("*.json")):
            task = json.loads(path.read_text())
            for rep in range(a.repeats):
                r = run_episode(task, agent)
                r.update(provider=a.provider, model=a.model, repeat=rep)
                f.write(json.dumps(r) + "\n")
                by_task.setdefault(task["task_id"], []).append(r["grade"]["reward"])
                print(f"{task['task_id']} rep{rep}: reward {r['grade']['reward']:.2f}  "
                      f"AUC24 {r['grade'].get('auc24_by_day')}")
    allr = [x for v in by_task.values() for x in v]
    print(f"\nMean reward {statistics.mean(allr):.3f} over {len(allr)} episodes. Saved: {out}")


if __name__ == "__main__":
    main()
