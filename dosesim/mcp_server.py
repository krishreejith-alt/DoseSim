"""MCP tool server: exposes one DoseSim episode to any MCP-capable agent harness.

Run:  DOSESIM_TASK=tasks/vanc/dose-vanc-0002.json python3 -m dosesim.mcp_server
Tools: get_labs, simulate, submit_dose (same rules as dosesim/tools.py).
The grade is written to DOSESIM_GRADE_OUT (default: grade.json) when the last day is submitted.
Hidden task fields are never returned to the agent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .env import DoseEnv
from .tools import TOOLS, call_tool

DESC = {t["name"]: t["description"] for t in TOOLS}


def build_server(task_path: str, grade_out: str = "grade.json") -> tuple[MCPServer, DoseEnv]:
    env = DoseEnv.from_file(task_path)
    server = MCPServer("dosesim", instructions=env.task["prompt"])

    @server.tool(description=DESC["get_labs"])
    def get_labs(day: int) -> dict:
        return call_tool(env, "get_labs", {"day": day})

    @server.tool(description=DESC["simulate"])
    def simulate(dose_mg: float, interval_h: float, days: int = 3,
                 loading_dose_mg: float | None = None) -> dict:
        return call_tool(env, "simulate", {"dose_mg": dose_mg, "interval_h": interval_h,
                                           "days": days, "loading_dose_mg": loading_dose_mg})

    @server.tool(description=DESC["submit_dose"])
    def submit_dose(day: int, dose_mg: float, interval_h: float, rationale: str,
                    loading_dose_mg: float | None = None) -> dict:
        out = call_tool(env, "submit_dose", {"day": day, "dose_mg": dose_mg, "interval_h": interval_h,
                                             "rationale": rationale, "loading_dose_mg": loading_dose_mg})
        if env.done:  # grade goes to the harness, not to the agent
            Path(grade_out).write_text(json.dumps({"grade": env.grade(), "log": env.log}, indent=2))
        return out

    return server, env


if __name__ == "__main__":
    srv, _ = build_server(os.environ["DOSESIM_TASK"], os.environ.get("DOSESIM_GRADE_OUT", "grade.json"))
    srv.run("stdio")
