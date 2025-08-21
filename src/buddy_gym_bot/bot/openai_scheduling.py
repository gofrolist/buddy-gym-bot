from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from ..config import SETTINGS
from ..exercisedb import ExerciseDBClient

# These functions are no longer needed since ExerciseDB data is uploaded once to OpenAI
# and referenced in the system prompt instead of being sent in every request.

SYSTEM_PROMPT = (
    "You are BuddyGym's coach. Produce ONLY JSON that validates against the provided schema. "
    "Respect the user's constraints (equipment/time/experience/days). "
    "When modifying an existing plan, preserve the current structure including days_per_week, "
    "exercise selection, and overall program design. Only change what is specifically requested. "
    "CRITICAL: You MUST use the file_search tool to find exercises from our ExerciseDB. "
    "1. Use file_search to search for exercises matching the user's request "
    "2. Extract the exercise_db_id from the search results "
    "3. Include ONLY exercises found through file_search in your response "
    "4. Return the exact exercise_db_id for each exercise in the plan "
    "DO NOT invent exercise names or use exercises not found through file_search. "
    "The file_search tool gives you access to our complete exercise database."
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
                                "exercise_db_id": {"type": "string"},
                                "equipment_ok": {"type": "array", "items": {"type": "string"}},
                                "target": {"type": "string"},
                                "exercise_db_name": {"type": ["string", "null"]},
                                "exercise_db_category": {"type": ["string", "null"]},
                                "exercise_db_equipment": {"type": ["string", "null"]},
                                "exercise_db_instructions": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                },
                                "is_validated": {"type": "boolean"},
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
                            "required": ["name", "exercise_db_id", "sets"],
                        },
                    },
                },
                "required": ["weekday", "exercises"],
            },
        },
    },
    "required": ["program_name", "weeks", "days_per_week", "days"],
}


def get_openai_vector_store_id() -> str | None:
    """Get the OpenAI vector store ID from environment variable."""
    vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
    if not vector_store_id:
        logging.warning(
            "OPENAI_VECTOR_STORE_ID environment variable not set. Run 'make upload-to-openai' first."
        )
        return None

    return vector_store_id


async def validate_and_enrich_exercises(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate exercises using Vector Store and enrich with metadata."""
    if not plan or "days" not in plan:
        return plan

    try:
        enriched_plan = plan.copy()

        for day in enriched_plan.get("days", []):
            for exercise in day.get("exercises", []):
                if isinstance(exercise, dict) and "exercise_db_id" in exercise:
                    # Type assertion to help the type checker
                    exercise_dict: dict[str, Any] = exercise
                    exercise_id = exercise["exercise_db_id"]

                    # Get exercise details by ID from local ExerciseDB data
                    exercise_db = ExerciseDBClient()
                    db_exercise = None

                    # Search for exercise by ID in local data
                    for db_exercise_item in exercise_db.exercises_data:
                        if db_exercise_item.get("exerciseId") == exercise_id:
                            db_exercise = {
                                "id": db_exercise_item.get("exerciseId"),
                                "name": db_exercise_item.get("name"),
                                "category": db_exercise_item.get("bodyParts", [""])[0]
                                if db_exercise_item.get("bodyParts")
                                else "",
                                "equipment": db_exercise_item.get("equipments", [""])[0]
                                if db_exercise_item.get("equipments")
                                else "",
                                "instructions": db_exercise_item.get("instructions", []),
                            }
                            break

                    if db_exercise:
                        # Exercise found - enrich with metadata
                        exercise_dict.update(
                            {
                                "exercise_db_name": db_exercise.get("name"),
                                "exercise_db_category": db_exercise.get("category"),
                                "exercise_db_equipment": db_exercise.get("equipment"),
                                "exercise_db_instructions": db_exercise.get("instructions", []),
                                "is_validated": True,
                                "validation_confidence": "openai_provided",
                                "match_quality": 1.0,
                            }
                        )

                        logging.info(
                            f"Exercise ID '{exercise_id}' enriched: {db_exercise.get('name')}"
                        )
                    else:
                        # This should never happen if OpenAI follows instructions
                        exercise_dict.update(
                            {
                                "is_validated": False,
                                "exercise_db_name": None,
                                "validation_confidence": "invalid_id",
                                "match_quality": 0.0,
                            }
                        )
                        logging.error(
                            f"Exercise ID '{exercise_id}' not found - OpenAI provided invalid ID"
                        )

        return enriched_plan
    except Exception as e:
        logging.error(f"Vector Store validation failed: {e}")
        return plan


def deterministic_fallback(
    text: str, tz: str, base_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    if base_plan:
        return base_plan

    # Use ExerciseDB exercises for fallback plan
    try:
        exercise_db = ExerciseDBClient()

        # Get some common exercises from ExerciseDB
        common_exercises = [
            exercise_db._find_best_match("squat"),
            exercise_db._find_best_match("barbell bench press"),
            exercise_db._find_best_match("bent over row"),
            exercise_db._find_best_match("deadlift"),
            exercise_db._find_best_match("overhead press"),
            exercise_db._find_best_match("pull-up"),
            exercise_db._find_best_match("front squat"),
            exercise_db._find_best_match("incline bench press"),
            exercise_db._find_best_match("lat pulldown"),
        ]

        # Filter out None results and get names
        exercise_names = [ex.get("name", "unknown") for ex in common_exercises if ex]

        # Fallback to hardcoded names if ExerciseDB fails
        if len(exercise_names) < 6:
            exercise_names = [
                "squat",
                "barbell bench press",
                "bent over row",
                "deadlift",
                "overhead press",
                "pull-up",
                "front squat",
                "incline bench press",
                "lat pulldown",
            ]

    except Exception as e:
        logging.error(f"Failed to get ExerciseDB exercises for fallback: {e}")
        exercise_names = [
            "squat",
            "barbell bench press",
            "bent over row",
            "deadlift",
            "overhead press",
            "pull-up",
            "front squat",
            "incline bench press",
            "lat pulldown",
        ]

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
                    {"name": exercise_names[0], "sets": [{"reps": "3x5"}]},
                    {"name": exercise_names[1], "sets": [{"reps": "3x5"}]},
                    {"name": exercise_names[2], "sets": [{"reps": "3x8"}]},
                ],
            },
            {
                "weekday": "Wed",
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": exercise_names[3], "sets": [{"reps": "1x5"}]},
                    {"name": exercise_names[4], "sets": [{"reps": "3x5"}]},
                    {"name": exercise_names[5], "sets": [{"reps": "3xAMRAP"}]},
                ],
            },
            {
                "weekday": "Fri",
                "time": "18:00",
                "focus": "Full Body",
                "exercises": [
                    {"name": exercise_names[6], "sets": [{"reps": "3x5"}]},
                    {"name": exercise_names[7], "sets": [{"reps": "3x8"}]},
                    {"name": exercise_names[8], "sets": [{"reps": "3x10"}]},
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
        # Use OpenAI Responses API with file_search tool to access uploaded ExerciseDB data
        # This eliminates the need to send exercise context in every request
        system_message = SYSTEM_PROMPT
        messages = [{"role": "system", "content": system_message}]

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
        # Use OpenAI Responses API with file_search tool
        input_text = f"Timezone: {tz}\nRequest: {text}\nSchema: {json.dumps(SCHEMA)}"

        if base_plan:
            input_text = f"Existing plan: {json.dumps(base_plan)}\n\nApply this request: {text}\nSchema: {json.dumps(SCHEMA)}"

        # Get OpenAI vector store ID for file_search tool
        vector_store_id = get_openai_vector_store_id()
        if not vector_store_id:
            logging.warning("No OpenAI vector_store_id available, falling back to local ExerciseDB")
            # Fallback to local search if OpenAI file not available
            return deterministic_fallback(text, tz, base_plan)

        # Use OpenAI Responses API with file_search tool
        payload = {
            "model": "gpt-5-mini",
            "input": input_text,
            "tools": [
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        vector_store_id
                    ],  # Use vector_store_ids with proper vs_ ID
                }
            ],
            "include": ["file_search_call.results"],
        }

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)

        # Use Responses API
        async with httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers=headers,
            timeout=timeout,
            http2=False,
        ) as client:
            last_err: Exception | None = None
            for i in range(3):
                try:
                    r = await client.post("/responses", json=payload)
                    if r.status_code >= 400:
                        try:
                            logging.error("openai_error_body: %s", r.text)
                        except Exception:
                            pass
                    r.raise_for_status()
                    response_data = r.json()

                    # Parse Responses API response format
                    content = ""
                    if "output" in response_data:
                        for output in response_data["output"]:
                            if output.get("type") == "message":
                                content = output.get("content", [{}])[0].get("text", "")
                                break

                    if not content:
                        logging.error("No content found in Responses API response")
                        return deterministic_fallback(text, tz, base_plan)

                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        logging.exception("Failed to parse OpenAI JSON: %r", content)
                        return deterministic_fallback(text, tz, base_plan)

                    for d in data.get("days", []):
                        wd = d.get("weekday")
                        if isinstance(wd, int) and 0 <= wd <= 6:
                            d["weekday"] = WEEKDAYS[wd]

                    # Validate and enrich exercises with ExerciseDB data
                    enriched_data = await validate_and_enrich_exercises(data)
                    return enriched_data

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
        fallback_plan = deterministic_fallback(text, tz, base_plan)
        # Still validate fallback exercises with ExerciseDB
        return await validate_and_enrich_exercises(fallback_plan)
