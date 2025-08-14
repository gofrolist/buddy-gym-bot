from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import SETTINGS

SYSTEM_PROMPT = (
    "You are BuddyGym's coach. Produce ONLY JSON that validates against the provided schema. "
    "Respect the user's constraints (equipment/time/experience/days). "
    "Prefer canonical exercise names from ExerciseDB when possible."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string"},
        "weeks": {"type": "integer", "minimum": 1},
        "days_per_week": {"type": "integer", "minimum": 1, "maximum": 7},
        "timezone": {"type": "string"},
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "weekday": {
                        "type": "string",
                        "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    },
                    "focus": {"type": "string"},
                    "time": {"type": "string"},
                    "duration_min": {"type": "integer"},
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "equipment_ok": {"type": "array", "items": {"type": "string"}},
                                "target": {"type": "string"},
                                "sets": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "reps": {"type": "string"},
                                            "load": {"type": "string"},
                                            "rest_sec": {"type": "integer"},
                                        },
                                        "required": ["reps"],
                                    },
                                },
                            },
                            "required": ["name", "sets"],
                        },
                    },
                },
                "required": ["weekday", "exercises"],
            },
        },
    },
    "required": ["program_name", "weeks", "days_per_week", "days"],
}


def deterministic_fallback(text: str, tz: str = "UTC") -> dict[str, Any]:
    """
    Return a simple fixed plan for Mon/Wed/Fri 18:00 as a fallback if OpenAI is unavailable.
    """
    plan = {
        "program_name": "BuddyGym 3x Full Body",
        "weeks": 4,
        "days_per_week": 3,
        "timezone": tz,
        "days": [],
    }
    days = [("Mon", "Full Body A"), ("Wed", "Upper Body"), ("Fri", "Lower Body")]
    for wk, (wd, focus) in enumerate(days):
        plan["days"].append(
            {
                "weekday": wd,
                "focus": focus,
                "time": "18:00",
                "duration_min": 40,
                "exercises": [
                    {
                        "name": "Barbell Squat",
                        "target": "quads",
                        "equipment_ok": ["barbell"],
                        "sets": [
                            {"reps": "5", "load": "moderate", "rest_sec": 120} for _ in range(3)
                        ],
                    },
                    {
                        "name": "Bench Press",
                        "target": "chest",
                        "equipment_ok": ["barbell", "dumbbell"],
                        "sets": [
                            {"reps": "5", "load": "moderate", "rest_sec": 120} for _ in range(3)
                        ],
                    },
                    {
                        "name": "Lat Pulldown",
                        "target": "lats",
                        "equipment_ok": ["cable"],
                        "sets": [
                            {"reps": "10-12", "load": "light-moderate", "rest_sec": 90}
                            for _ in range(3)
                        ],
                    },
                ],
            }
        )
    return plan


async def generate_schedule(text: str, tz: str = "UTC") -> dict[str, Any]:
    """
    Generate a workout schedule using OpenAI if API key is set, otherwise use deterministic fallback.
    """
    if not SETTINGS.OPENAI_API_KEY:
        return deterministic_fallback(text, tz)
    try:
        headers = {"Authorization": f"Bearer {SETTINGS.OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Timezone: {tz}\nRequest: {text}\nSchema: {json.dumps(SCHEMA)}",
                },
            ],
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", json=payload)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        logging.exception("OpenAI schedule generation failed, using fallback: %s", e)
        return deterministic_fallback(text, tz)
