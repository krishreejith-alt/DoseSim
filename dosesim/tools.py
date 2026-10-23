"""Tool definitions shown to the AI agent (one source of truth for every adapter: runner, MCP, verifiers).

Only these three tools exist. Hidden task fields are never exposed.
"""

TOOLS = [
    {
        "name": "get_labs",
        "description": ("Patient labs available so far: demographics, serum creatinine for each day up to "
                        "the requested day, and any vancomycin levels already resulted. "
                        "You can't request a day later than today."),
        "parameters": {
            "type": "object",
            "properties": {"day": {"type": "integer", "description": "Day number, 0 = admission day."}},
            "required": ["day"],
        },
    },
    {
        "name": "simulate",
        "description": ("What-if calculator using the published population PK model and today's kidney function. "
                        "Returns predicted AUC24 per day and the last trough. It does not know this patient's "
                        "individual drug handling, so measured levels may differ."),
        "parameters": {
            "type": "object",
            "properties": {
                "dose_mg": {"type": "number"},
                "interval_h": {"type": "number", "enum": [8, 12, 24]},
                "days": {"type": "integer", "minimum": 1, "maximum": 7},
                "loading_dose_mg": {"type": "number"},
            },
            "required": ["dose_mg", "interval_h"],
        },
    },
    {
        "name": "submit_dose",
        "description": ("Set the regimen that starts today and continues until you change it. "
                        "One submission per day, in order. Loading dose only on day 0 "
                        "(max 35 mg/kg and 3000 mg). Include a short clinical rationale."),
        "parameters": {
            "type": "object",
            "properties": {
                "day": {"type": "integer"},
                "dose_mg": {"type": "number"},
                "interval_h": {"type": "number", "enum": [8, 12, 24]},
                "rationale": {"type": "string"},
                "loading_dose_mg": {"type": "number"},
            },
            "required": ["day", "dose_mg", "interval_h", "rationale"],
        },
    },
]


def call_tool(env, name: str, args: dict) -> dict:
    """Run one tool call against a DoseEnv. Bad names or arguments return an error, never crash."""
    try:
        if name == "get_labs":
            return env.get_labs(int(args["day"]))
        if name == "simulate":
            return env.simulate(float(args["dose_mg"]), float(args["interval_h"]),
                                int(args.get("days", 3)), args.get("loading_dose_mg"))
        if name == "submit_dose":
            return env.submit_dose(int(args["day"]), float(args["dose_mg"]), float(args["interval_h"]),
                                   str(args.get("rationale", "")), args.get("loading_dose_mg"))
        return {"error": f"unknown tool {name}"}
    except (KeyError, TypeError, ValueError) as e:
        return {"error": f"bad arguments: {e}"}
