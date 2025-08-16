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

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
                    "weekday": {"type": "string", "enum": WEEKDAYS},
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


def deterministic_fallback(
    text: str, tz: str, base_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    if base_plan:
        return base_plan
    return {
        "program_name": "Fallback Plan",
        "timezone": tz or "UTC",
        "weeks": 1,
        "days_per_week": 3,
        "days": [
            {
                "weekday": "Mon",
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": "squat", "sets": [{"reps": "3x5"}]},
                    {"name": "bench press", "sets": [{"reps": "3x5"}]},
                    {"name": "row", "sets": [{"reps": "3x8"}]},
                ],
            },
            {
                "weekday": "Wed",
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": "deadlift", "sets": [{"reps": "1x5"}]},
                    {"name": "overhead press", "sets": [{"reps": "3x5"}]},
                    {"name": "pull-up", "sets": [{"reps": "3xAMRAP"}]},
                ],
            },
            {
                "weekday": "Fri",
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


async def generate_schedule(
    text: str, tz: str = "UTC", base_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not SETTINGS.OPENAI_API_KEY:
        return deterministic_fallback(text, tz, base_plan)
    try:
        headers = {
            "Authorization": f"Bearer {SETTINGS.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if base_plan:
            messages.append(
                {
                    "role": "user",
                    "content": f"Existing plan: {json.dumps(base_plan)}",
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"Apply this request: {text}\nSchema: {json.dumps(SCHEMA)}",
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": f"Timezone: {tz}\nRequest: {text}\nSchema: {json.dumps(SCHEMA)}",
                }
            )
        payload = {
            "model": "gpt-5-mini",
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
        async with httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers=headers,
            timeout=timeout,
            http2=False,
        ) as client:
            last_err: Exception | None = None
            for i in range(3):
                try:
                    r = await client.post("/chat/completions", json=payload)
                    if r.status_code >= 400:
                        try:
                            logging.error("openai_error_body: %s", r.text)
                        except Exception:
                            pass
                    r.raise_for_status()
                    content = r.json()["choices"][0]["message"]["content"]
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        logging.exception("Failed to parse OpenAI JSON: %r", content)
                        return deterministic_fallback(text, tz, base_plan)
                    for d in data.get("days", []):
                        wd = d.get("weekday")
                        if isinstance(wd, int) and 0 <= wd <= 6:
                            d["weekday"] = WEEKDAYS[wd]
                    return data
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                    last_err = e
                    if i < 2:
                        await asyncio.sleep(0.75 * (2**i))
                        continue
                    raise
                except httpx.HTTPError as e:
                    last_err = e
                    raise
            raise last_err or RuntimeError("OpenAI failure")
    except Exception as e:
        logging.exception("OpenAI schedule generation failed, using fallback: %s", e)
        return deterministic_fallback(text, tz, base_plan)
