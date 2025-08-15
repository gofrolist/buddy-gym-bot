from __future__ import annotations

import asyncio
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

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string"},
        "timezone": {"type": "string"},
        "weeks": {"type": "integer", "minimum": 1, "maximum": 12},
        "days_per_week": {"type": "integer", "minimum": 1, "maximum": 7},
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "weekday": {"type": "integer", "minimum": 0, "maximum": 6},
                    "time": {"type": "string", "pattern": "^[0-2][0-9]:[0-5][0-9]$"},
                    "focus": {"type": "string"},
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


def deterministic_fallback(text: str, tz: str) -> dict[str, Any]:
    return {
        "program_name": "Fallback Plan",
        "timezone": tz or "UTC",
        "weeks": 1,
        "days_per_week": 3,
        "days": [
            {
                "weekday": 0,
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": "squat", "sets": [{"reps": "3x5"}]},
                    {"name": "bench press", "sets": [{"reps": "3x5"}]},
                    {"name": "row", "sets": [{"reps": "3x8"}]},
                ],
            },
            {
                "weekday": 2,
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": "deadlift", "sets": [{"reps": "1x5"}]},
                    {"name": "overhead press", "sets": [{"reps": "3x5"}]},
                    {"name": "pull-up", "sets": [{"reps": "3xAMRAP"}]},
                ],
            },
            {
                "weekday": 4,
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": "front squat", "sets": [{"reps": "3x5"}]},
                    {"name": "incline bench", "sets": [{"reps": "3x8"}]},
                    {"name": "lat pulldown", "sets": [{"reps": "3x10"}]},
                ],
            },
        ],
    }


async def generate_schedule(text: str, tz: str = "UTC") -> dict[str, Any]:
    if not SETTINGS.OPENAI_API_KEY:
        return deterministic_fallback(text, tz)
    try:
        headers = {
            "Authorization": f"Bearer {SETTINGS.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-5-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Timezone: {tz}\nRequest: {text}\nSchema: {json.dumps(SCHEMA)}",
                },
            ],
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            try:
                r = await client.post("https://api.openai.com/v1/chat/completions", json=payload)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response else "unknown"
                if status == 401:
                    logging.warning("OpenAI unauthorized (401). Using deterministic fallback.")
                else:
                    logging.warning(
                        "OpenAI request failed (%s). Using deterministic fallback.", status
                    )
                return deterministic_fallback(text, tz)
            except httpx.HTTPError as e:
                logging.warning("OpenAI request failed: %s. Using deterministic fallback.", e)
                return deterministic_fallback(text, tz)
            content = r.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logging.exception("Failed to parse OpenAI JSON: %r", content)
                return deterministic_fallback(text, tz)
    except Exception as e:  # pragma: no cover - defensive
        logging.exception("OpenAI schedule generation failed, using fallback: %s", e)
        return deterministic_fallback(text, tz)
