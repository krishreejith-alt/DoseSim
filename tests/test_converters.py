"""API message converters: checked offline so a live run doesn't fail on formatting."""

from scripts.run_model import to_anthropic, to_openai

MSGS = [
    {"role": "user", "content": "task prompt"},
    {"role": "user", "content": "Day 0, morning."},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "a1", "name": "get_labs", "args": {"day": 0}}]},
    {"role": "tool", "tool_call_id": "a1", "name": "get_labs", "content": "{}"},
    {"role": "user", "content": "Please submit the day 0 regimen."},
]


def test_anthropic_roles_alternate_and_results_first():
    out = to_anthropic(MSGS)
    roles = [m["role"] for m in out]
    assert all(a != b for a, b in zip(roles, roles[1:]))
    last_user = out[-1]["content"]
    assert last_user[0]["type"] == "tool_result" and last_user[-1]["type"] == "text"


def test_openai_tool_call_shape():
    out = to_openai(MSGS)
    assert out[0]["role"] == "system"
    call = [m for m in out if m["role"] == "assistant"][0]["tool_calls"][0]
    assert call["function"]["name"] == "get_labs" and call["type"] == "function"
    assert any(m["role"] == "tool" and m["tool_call_id"] == "a1" for m in out)
