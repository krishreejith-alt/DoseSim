"""MCP server: tools register, run, and write the grade only at the end."""

import asyncio
import json
from pathlib import Path

from dosesim.mcp_server import build_server

TASK = Path(__file__).resolve().parent.parent / "tasks" / "vanc" / "dose-vanc-0001.json"


def test_tools_listed_and_episode_grades(tmp_path):
    out = tmp_path / "grade.json"
    server, env = build_server(str(TASK), str(out))

    async def go():
        names = {t.name for t in await server.list_tools()}
        assert names == {"get_labs", "simulate", "submit_dose"}
        await server.call_tool("get_labs", {"day": 0})
        for d in range(env.n_days):
            await server.call_tool("submit_dose", {"day": d, "dose_mg": 1250, "interval_h": 12,
                                                   "rationale": "creatinine clearance based"})
    asyncio.run(go())
    data = json.loads(out.read_text())
    assert 0 <= data["grade"]["reward"] <= 1
