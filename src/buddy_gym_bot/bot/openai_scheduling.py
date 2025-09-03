from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache
from typing import Any, cast

import httpx

from ..config import SETTINGS
from ..exercisedb import ExerciseDBClient

# Very small alias list for generic names (doesn't force user locale; just helps common cases)
ALIAS = {
    "bench press": "dumbbell bench press",
    "overhead press": "dumbbell standing overhead press",
    "bent over row": "barbell bent over row",
    "face pulls": "cable rear delt row (with rope)",
    "face pull": "cable rear delt row (with rope)",
    "plank": "weighted front plank",  # closest canonical variant in many dbs
    "squat": "barbell full squat",
    "squats": "barbell full squat",
    "rdl": "barbell romanian deadlift",
    "romanian deadlift": "barbell romanian deadlift",
    "glute bridge": "glute bridge two legs on bench (male)",
    "seated calf raises": "lever seated calf raise",
    "seated calf raise": "lever seated calf raise",
    "step ups": "dumbbell step-up",
    "step ups alternating": "dumbbell step-up",
    "reverse lunge": "dumbbell rear lunge",
    "reverse lunges": "dumbbell rear lunge",
    "single arm dumbbell row": "dumbbell one arm bent-over row",
    "lat pulldown": "cable lat pulldown full range of motion",
    "seated row": "cable rope seated row",
    "bicycle crunches": "air bike",
    "push ups": "push-up",
    "pushups": "push-up",
}


def _normalize_name(s: str) -> str:
    """ASCII-fold for non-English diacritics, lowercase, strip brackets and punctuation."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\(.*?\)", " ", s)  # drop parentheses content
    s = s.replace("-", " ").replace("/", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)  # keep alnum + spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


@lru_cache(maxsize=1)
def _build_exercise_indexes() -> tuple[
    list[str], list[str], dict[str, str], defaultdict[str, set[int]]
]:
    """
    Returns:
      names: list of canonical names
      ids:   parallel list of IDs
      norm_to_id: exact normalized-name -> id
      token_index: token -> set(idx positions) for fast candidate narrowing
    """
    db = ExerciseDBClient()  # uses your existing loader with full data
    items: list[dict[str, Any]] = db.exercises_data  # [{'exerciseId','name',...}, ...]
    names: list[str] = []
    ids: list[str] = []
    for x in items:
        n = (x.get("name") or "").strip()
        i = x.get("exerciseId")
        if n and i:
            names.append(n)
            ids.append(i)

    norm_to_id = {_normalize_name(n): i for n, i in zip(names, ids, strict=False)}

    # token-based inverted index
    token_index: defaultdict[str, set[int]] = defaultdict(set)
    for idx, n in enumerate(names):
        for tok in _normalize_name(n).split():
            if tok:
                token_index[tok].add(idx)

    return names, ids, norm_to_id, token_index


def _alias_or_same(norm_name: str) -> str:
    """Apply alias on the normalized form."""
    # map ALIAS keys via normalize to be robust
    _aliased = {_normalize_name(k): _normalize_name(v) for k, v in ALIAS.items()}
    return _aliased.get(norm_name, norm_name)


def _resolve_exercise_id_by_name(name: str) -> tuple[str | None, str, str]:
    """
    Returns: (exercise_id or None, matched_name, method)
      method in {"exact","alias","fuzzy","none"}
    """
    if not name:
        return (None, "", "none")

    names, ids, norm_to_id, token_index = _build_exercise_indexes()
    norm = _normalize_name(name)

    # 1) exact normalized name
    if norm in norm_to_id:
        return (norm_to_id[norm], name, "exact")

    # 2) alias -> exact
    aliased = _alias_or_same(norm)
    if aliased != norm and aliased in norm_to_id:
        return (norm_to_id[aliased], name, "alias")

    # 3) token-narrowed fuzzy match (difflib on candidates only)
    toks = set(aliased.split())
    candidates: set[int] = set()
    for t in toks:
        candidates |= token_index.get(t, set())

    # if no candidates from tokens, consider all names (still bounded by difflib)
    pool = [names[i] for i in candidates] if candidates else names

    # try a decent ratio threshold; tokenized strings tend to match >= 0.84 when close
    best_id: str | None = None
    best_ratio: float = 0.0
    for cand in pool[:5000]:  # safeguard
        r = difflib.SequenceMatcher(None, _normalize_name(cand), aliased).ratio()
        if r > best_ratio:
            best_ratio, best_id = r, ids[names.index(cand)]
            if best_ratio >= 0.93:
                break
    if best_ratio >= 0.84:
        return (best_id, name, "fuzzy")

    return (None, name, "none")


# These functions are no longer needed since ExerciseDB data is uploaded once to OpenAI
# and referenced in the system prompt instead of being sent in every request.

SYSTEM_PROMPT = (
    "You are BuddyGym's AI coach. Your task is to create workout plans based on user requests.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "1. ALWAYS return only JSON that matches the schema (no prose)\n"
    "2. Follow the user's requirements exactly as specified\n"
    "3. Select exercises that match the user's request\n"
    "4. Create a realistic, balanced workout plan with appropriate sets and reps\n"
    "5. Return a complete workout plan in valid JSON format\n"
    "6. If modifying an existing plan, preserve the user's requested changes exactly"
)


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "program_name": {"type": "string"},
        "timezone": {"type": "string"},
        "weeks": {"type": "integer"},  # clamp 1..12 in code
        "days_per_week": {"type": "integer"},  # clamp 1..7 in code
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "weekday": {"type": "string"},  # validate in code
                    "time": {"type": "string"},  # validate "HH:MM" in code
                    "focus": {"type": "string"},
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "sets": {"type": "integer"},  # clamp ≥1 in code
                                "reps": {"type": "string"},
                            },
                            "required": ["name", "sets", "reps"],  # exercise_db_id removed
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["weekday", "time", "focus", "exercises"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["program_name", "timezone", "weeks", "days_per_week", "days"],
    "additionalProperties": False,
}


def build_constraints_schema() -> dict[str, Any]:
    """Build constraints schema programmatically to ensure required matches properties exactly."""
    properties: dict[str, Any] = {
        "days": {
            "type": "array",
            "items": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
        },
        "days_per_week": {"type": "integer"},  # use 0 when unknown; clamp later
        "duration_minutes": {"type": "integer", "enum": [30, 45, 60]},
        "weeks": {"type": "integer"},  # use 0 when unknown; clamp later
        "time": {"type": "string"},  # "" when unknown; validate "HH:MM" later
        "program_split": {"type": "string"},  # "" or "custom" if unspecified
        "per_day_focus": {"type": "string"},  # "" when unknown
        "equipment": {"type": "string"},  # "" when unknown
        "language": {"type": "string"},  # "" when unknown
    }

    required: list[str] = list(properties.keys())  # MUST match exactly
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }

    # Safety assert + helpful log (keeps you from shipping a mismatched schema)
    missing = [k for k in properties if k not in required]
    extra = [k for k in required if k not in properties]
    if missing or extra:
        # log and raise early; this is the error you're seeing from the API
        logging.error("Constraints schema mismatch. missing=%s extra=%s", missing, extra)
        raise RuntimeError("Constraints schema required <> properties mismatch")

    return schema


# Build schema programmatically to prevent mismatches
CONSTRAINTS_SCHEMA = build_constraints_schema()

# Constraint sanitization and day resolution functions


def sanitize_constraints(c: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and validate constraints from GPT-5 output."""
    out: dict[str, Any] = dict(c or {})

    dm = out.get("duration_minutes")
    out["duration_minutes"] = dm if dm in (30, 45, 60) else 30

    dpw = out.get("days_per_week") or 0
    out["days_per_week"] = max(0, min(int(dpw), 7)) if isinstance(dpw, int) else 0

    days = [
        d for d in (out.get("days") or []) if d in {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    ]
    seen: set[str] = set()
    days = [d for d in days if not (d in seen or seen.add(d))]
    out["days"] = days

    w = out.get("weeks") or 0
    out["weeks"] = max(1, min(int(w), 12)) if isinstance(w, int) and w > 0 else 1

    t = out.get("time")
    out["time"] = (
        t
        if (
            isinstance(t, str)
            and len(t) == 5
            and t[2] == ":"
            and t[:2].isdigit()
            and t[3:].isdigit()
        )
        else None
    )

    ps = out.get("program_split") or "custom"
    out["program_split"] = ps if ps else "custom"

    # Fix: Ensure per_day_focus is a dict, not empty string
    pf = out.get("per_day_focus")
    if not isinstance(pf, dict) or not pf:
        out["per_day_focus"] = {}

    out["equipment"] = out.get("equipment") or ""
    out["language"] = out.get("language") or ""

    return out


def resolve_requested_days(c: dict[str, Any]) -> list[str]:
    """Resolve requested days from constraints, with fallback to days_per_week presets."""
    if c["days"]:
        return c["days"]
    dpw = c.get("days_per_week") or 3
    presets: dict[int, list[str]] = {
        1: ["Wed"],
        2: ["Tue", "Thu"],
        3: ["Mon", "Wed", "Fri"],
        4: ["Mon", "Tue", "Thu", "Sat"],
        5: ["Mon", "Tue", "Wed", "Thu", "Fri"],
        6: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        7: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }
    return presets.get(dpw, ["Mon", "Wed", "Fri"])


async def extract_constraints(raw_text: str) -> dict[str, Any] | None:
    """Extract workout constraints from user messages in any language."""
    if not SETTINGS.OPENAI_API_KEY:
        return None

    try:
        headers = {
            "Authorization": f"Bearer {SETTINGS.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        # Quick self-test (before calling the API)
        schema = build_constraints_schema()
        props = set(schema["properties"].keys())
        req = set(schema["required"])
        logging.info("Constraints schema keys=%s", sorted(props))
        logging.info("Constraints schema required=%s", sorted(req))
        assert props == req, f"Schema mismatch props != required: {props ^ req}"

        payload = {
            "model": "gpt-5-mini",
            "input": (
                "Extract workout constraints from the user message.\n"
                "Always include ALL fields below. If not specified by the user, use placeholders:\n"
                "- days: []\n"
                "- days_per_week: 0\n"
                "- weeks: 0\n"
                '- time: ""\n'
                '- program_split: "custom"\n'
                '- per_day_focus: ""\n'
                '- equipment: ""\n'
                '- language: ""\n'
                "Return ONLY JSON matching the schema."
                f"\n\nUser request:\n{raw_text}"
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "Constraints",  # REQUIRED
                    "schema": CONSTRAINTS_SCHEMA,
                    "strict": True,
                }
            },
            "store": True,
        }

        timeout = httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=60.0)

        async with httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers=headers,
            timeout=timeout,
            http2=False,
        ) as client:
            try:
                r = await client.post("/responses", json=payload)
                r.raise_for_status()
                response_data = r.json()

                # Extract content from response
                content = _extract_text_from_response(response_data)

                if not content:
                    logging.warning("No content found in constraints extraction response")
                    return None

                # Parse the constraints JSON
                try:
                    raw = json.loads(content)  # from Step A
                    constraints = sanitize_constraints(raw)
                    logging.info(f"Extracted and sanitized constraints: {constraints}")
                    return constraints
                except json.JSONDecodeError:
                    complete = _extract_complete_json(content)
                    if not complete:
                        logging.warning("Failed to recover complete JSON from model output")
                        return None
                    try:
                        raw = json.loads(complete)
                        constraints = sanitize_constraints(raw)
                        logging.info(
                            f"Recovered and sanitized constraints from incomplete JSON: {constraints}"
                        )
                        return constraints
                    except json.JSONDecodeError:
                        logging.warning("Failed to parse recovered constraints JSON")
                        return None

            except httpx.HTTPStatusError as e:
                logging.error(
                    "OpenAI API HTTP error during constraint extraction: %s %s",
                    e.response.status_code,
                    (e.response.text or "")[:500],
                )
                return None
            except Exception as e:
                logging.error(f"OpenAI API error during constraint extraction: {e}")
                return None

    except Exception as e:
        logging.exception(f"Constraint extraction failed: {e}")
        return None


async def call_plan_generator(
    constraints: dict[str, Any], tz: str, requested_days: list[str]
) -> dict[str, Any] | None:
    """Generate a workout plan based on extracted constraints."""
    if not SETTINGS.OPENAI_API_KEY:
        return None

    try:
        headers = {
            "Authorization": f"Bearer {SETTINGS.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        # Build input text with constraints JSON and EXPLICIT day requirements
        constraints_json = json.dumps(constraints, indent=2)

        input_text = (
            "You are a workout planner. Return ONLY JSON that matches the WorkoutPlan schema. No extra text.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- You MUST create exactly {len(requested_days)} days: {', '.join(requested_days)}\n"
            "- Each day MUST have exercises array with 4-5 exercises for 30min, 5-6 for 45min, or 6-8 for 60min\n"
            "- Use DIFFERENT exercises for each day to avoid repetition\n"
            "- Consider muscle group variety across days\n"
            "- Each exercise MUST have: name, sets, reps ONLY\n"
            "- IMPORTANT: Use common, standard exercise names (e.g., 'Push-ups', 'Squats', 'Bench Press')\n"
            "- DO NOT include exercise_db_id - leave IDs to the system\n"
            "- Output fields for exercises: name, sets, reps ONLY. Do NOT include any exercise_db_id or ID fields\n"
            "- Focus on creating a balanced, varied workout plan\n\n"
            f"Required days: {requested_days}\n"
            f"Duration: {constraints.get('duration_minutes', 60)} minutes\n"
            f"Constraints: {constraints_json}\n"
            f"Timezone: {tz}"
        )

        payload = {
            "model": "gpt-5-mini",
            "input": input_text,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "WorkoutPlan",  # REQUIRED
                    "schema": SCHEMA,
                    "strict": True,
                }
            },
            "store": True,
        }

        timeout = httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=60.0)

        async with httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers=headers,
            timeout=timeout,
            http2=False,
        ) as client:
            try:
                r = await client.post("/responses", json=payload)
                r.raise_for_status()
                response_data = r.json()

                # Extract content from response
                content = _extract_text_from_response(response_data)

                if not content:
                    logging.warning("No content found in plan generation response")
                    return None

                # Parse the plan JSON
                try:
                    plan = json.loads(content)
                    logging.info(f"Generated plan with {len(plan.get('days', []))} days")
                    return plan
                except json.JSONDecodeError:
                    complete = _extract_complete_json(content)
                    if not complete:
                        logging.warning("Failed to recover complete JSON from model output")
                        return None
                    try:
                        plan = json.loads(complete)
                        logging.info(
                            f"Recovered plan from incomplete JSON with {len(plan.get('days', []))} days"
                        )
                        return plan
                    except json.JSONDecodeError:
                        logging.warning("Failed to parse recovered plan JSON")
                        return None

            except httpx.HTTPStatusError as e:
                logging.error(
                    "OpenAI API HTTP error during plan generation: %s %s",
                    e.response.status_code,
                    (e.response.text or "")[:500],
                )
                return None
            except Exception as e:
                logging.error(f"OpenAI API error during plan generation: {e}")
                return None

    except Exception as e:
        logging.exception(f"Plan generation failed: {e}")
        return None


def _extract_complete_json(json_text: str) -> str | None:
    """Extract a complete JSON object from potentially incomplete text."""
    try:
        # Find the last complete JSON object by counting braces
        brace_count = 0
        start_pos = -1
        last_complete = None

        for i, char in enumerate(json_text):
            if char == "{":
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    # Found a complete object
                    last_complete = json_text[start_pos : i + 1]
                    start_pos = -1  # Reset for next potential object

        return last_complete
    except Exception as e:
        logging.warning(f"Error extracting complete JSON: {e}")
        return None


def _validate_and_fix_plan(
    plan: dict[str, Any], constraints: dict[str, Any], requested_days: list[str]
) -> dict[str, Any]:
    """Validate and fix the AI-generated plan to ensure it follows user requirements."""
    if not plan or "days" not in plan:
        return plan

    logging.info(f"Validating plan for constraints: {constraints}")
    logging.info(f"Requested days: {requested_days}")
    logging.info(f"Original plan has {len(plan.get('days', []))} days")

    # Extract requirements from constraints
    duration_minutes: int = int(cast(Any, constraints.get("duration_minutes", 30)) or 30)

    logging.info(f"Requested duration: {duration_minutes} minutes")

    # Fix the plan if needed
    fixed_plan: dict[str, Any] = dict(plan)

    # Ensure only the requested days are used
    if requested_days and len(requested_days) > 0:
        current_days = [
            cast(dict[str, Any], day).get("weekday") for day in cast(list, plan.get("days", []))
        ]
        logging.info(f"User requested days: {requested_days}")
        logging.info(f"AI generated days: {current_days}")

        # Check if the AI used the correct days
        if set(current_days) != set(requested_days):
            logging.warning(f"AI used wrong days: {current_days}, expected: {requested_days}")
            # Keep only the requested days, remove others
            fixed_plan["days"] = [
                day
                for day in cast(list, plan.get("days", []))
                if cast(dict[str, Any], day).get("weekday") in requested_days
            ]
            # Update days_per_week
            fixed_plan["days_per_week"] = len(fixed_plan["days"])

    # If no day objects remain after trimming, create empty shells for requested days
    if requested_days and not fixed_plan.get("days"):
        logging.warning(
            "No valid days found after trimming, creating empty shells for requested days"
        )
        default_time = constraints.get("time") or "19:00"
        fixed_plan["days"] = [
            {"weekday": d, "time": default_time, "focus": "", "exercises": []}
            for d in requested_days
        ]
        fixed_plan["days_per_week"] = len(requested_days)

    # Ensure each day has exercises (no specific count requirements)
    for day in cast(list, fixed_plan.get("days", [])):
        day_dict = cast(dict[str, Any], day)
        # Validate and fix weekday if needed
        weekday: str = str(day_dict.get("weekday", ""))
        valid_weekdays = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
        if weekday not in valid_weekdays:
            # Find the first valid weekday from requested days
            if requested_days:
                day_dict["weekday"] = requested_days[0]
                logging.info(f"Fixed invalid weekday '{weekday}' to '{requested_days[0]}'")
            else:
                day_dict["weekday"] = "Mon"
                logging.info(f"Fixed invalid weekday '{weekday}' to 'Mon'")

        # Validate and fix time if needed
        day_time: str = str(day_dict.get("time", ""))
        if not day_time or not re.match(r"^[0-2][0-9]:[0-5][0-9]$", day_time):
            default_time: str = str(constraints.get("time") or "19:00")
            day_dict["time"] = default_time
            logging.info(
                f"Fixed invalid time '{day_time}' to '{default_time}' for {day_dict.get('weekday')}"
            )

        exercises: list[dict[str, Any]] = [
            cast(dict[str, Any], e) for e in cast(list, day_dict.get("exercises", []))
        ]

        # Deduplicate exercises to prevent multiple identical exercises
        seen_exercises: set[str] = set()
        unique_exercises: list[dict[str, Any]] = []
        for ex in exercises:
            ex_name: str = str(ex.get("name", "")).lower().strip()
            if ex_name and ex_name not in seen_exercises:
                seen_exercises.add(ex_name)
                unique_exercises.append(ex)
            elif ex_name:
                logging.info(
                    f"Removing duplicate exercise '{ex.get('name')}' from {day_dict.get('weekday')}"
                )

        # Replace exercises list with deduplicated version
        exercises = unique_exercises
        day_dict["exercises"] = exercises

        # Determine targets by duration
        min_max: dict[int, tuple[int, int]] = {30: (4, 5), 45: (5, 6), 60: (6, 8)}
        mn, mx = min_max.get(int(duration_minutes), (4, 5))

        # Clamp sets per duration
        if duration_minutes == 30:
            for e in exercises:
                e["sets"] = 3
        else:  # 45 or 60
            for e in exercises:
                try:
                    s = int(cast(Any, e.get("sets", 3)))
                except Exception:
                    s = 3
                e["sets"] = min(max(s, 3), 4)

        # No top-up - let the plan be exactly what the user requested
        # If the AI generated fewer exercises than expected, that's the user's plan

        # Trim if long (but don't add if short)
        if len(exercises) > mx:
            logging.info(
                f"Reducing exercises from {len(exercises)} to {mx} on {day.get('weekday')} "
                f"(too many for {duration_minutes} min duration)"
            )
            exercises = exercises[:mx]

        day_dict["exercises"] = exercises
        logging.info(
            f"Day {day_dict.get('weekday')} has {len(exercises)} exercises for {duration_minutes} min duration"
        )

    # Sort days and sync counters before returning
    order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    fixed_plan["days"] = sorted(
        cast(list, fixed_plan.get("days", [])),
        key=lambda d: order.get(cast(dict[str, Any], d).get("weekday", "Mon"), 0),
    )
    fixed_plan["days_per_week"] = len(fixed_plan["days"])

    return fixed_plan


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
                            }
                            break

                    if db_exercise:
                        # Exercise found - enrich with metadata
                        exercise_dict.update(
                            {
                                "exercise_db_name": db_exercise.get("name"),
                                "exercise_db_category": db_exercise.get("category"),
                                "exercise_db_equipment": db_exercise.get("equipment"),
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


def _fill_missing_or_invalid_ids(plan: dict) -> dict:
    """Fill missing or invalid exercise_db_id values by mapping exercise names to IDs."""
    try:
        db = ExerciseDBClient()
        valid_ids = {x.get("exerciseId") for x in db.exercises_data if x.get("exerciseId")}

        for day in plan.get("days", []):
            seen_ids = set()  # per-day de-dupe
            unique_exercises = []

            for ex in day.get("exercises", []):
                ex = dict(ex)  # copy

                ex_id = ex.get("exercise_db_id")
                # if id missing or invalid, try to resolve from name
                if not ex_id or ex_id not in valid_ids:
                    resolved_id, _, method = _resolve_exercise_id_by_name(ex.get("name", ""))
                    if resolved_id:
                        ex["exercise_db_id"] = resolved_id
                        ex["is_validated"] = True
                        ex["validation_confidence"] = (
                            "mapped_from_name" if method != "exact" else "openai_provided"
                        )
                    else:
                        # mark as unmapped so you can message the user, but keep the name
                        ex["is_validated"] = False
                        ex["validation_confidence"] = "unmapped_exercise"

                # final guard: if still invalid, skip to next exercise
                if ex.get("exercise_db_id") not in valid_ids:
                    unique_exercises.append(ex)  # keep for UI, but it won't enrich
                    continue

                # per-day duplicate guard
                if ex["exercise_db_id"] in seen_ids:
                    # try to pick a safe alternative of similar pattern using alias seed
                    alt_id, _, method = _resolve_exercise_id_by_name(
                        ALIAS.get(_normalize_name(ex.get("name", "")), "push-up")
                    )
                    if alt_id and alt_id not in seen_ids:
                        ex["exercise_db_id"] = alt_id
                        ex["validation_confidence"] = "duplicate_replaced_" + method
                    else:
                        # if we still collide, just skip this duplicate
                        continue

                seen_ids.add(ex["exercise_db_id"])
                unique_exercises.append(ex)

            day["exercises"] = unique_exercises

        return plan
    except Exception as e:
        logging.warning(f"Failed to fill exercise IDs: {e}")
        return plan


def _extract_text_from_response(resp_json: dict) -> str:
    """Collect assistant-visible text from Responses API output items."""
    out = []

    # New Responses API structure: top-level "output" is a list of items
    for item in resp_json.get("output", []):
        if item.get("type") == "message":
            for block in item.get("content", []):
                # Responses API block
                if block.get("type") == "output_text":
                    out.append(block.get("text") or block.get("value") or "")
                # Messages API block (older shape) - keep for compatibility
                elif block.get("type") == "text":
                    text_obj = block.get("text", {})
                    out.append(text_obj.get("value") or text_obj.get("content") or "")
        # Handle reasoning responses (for test compatibility)
        elif item.get("type") == "reasoning":
            for block in item.get("content", []):
                if block.get("type") == "text":
                    text_obj = block.get("text", {})
                    out.append(text_obj.get("value") or text_obj.get("content") or "")
        # Rare: some models put plain "output_text" at top-level
        elif item.get("type") == "output_text":
            out.append(item.get("text") or item.get("value") or "")

    return "\n".join([s for s in out if s]).strip()


async def generate_schedule(
    text: str, tz: str = "UTC", base_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Generate a workout schedule using the new two-step approach."""
    if not SETTINGS.OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured. Cannot generate workout plan.")

    try:
        # Step A: Extract constraints from user text (multilingual)
        logging.info(f"Step A: Extracting constraints from user text: {text}")
        constraints = await extract_constraints(text)

        if not constraints or "duration_minutes" not in constraints:
            logging.error("Constraint extraction failed. Please try again or create plan manually.")
            raise ValueError(
                "Failed to extract workout constraints. Please rephrase your request or create a plan manually."
            )

        # Resolve requested days (with fallback to days_per_week presets)
        requested_days = resolve_requested_days(constraints)
        if not requested_days:
            logging.error(
                "Could not determine workout days. Please try again or create plan manually."
            )
            raise ValueError(
                "Failed to determine workout days. Please rephrase your request or create a plan manually."
            )

        logging.info(f"Successfully extracted constraints: {constraints}")
        logging.info(f"Resolved requested days: {requested_days}")

        # Step B: Generate plan based on constraints
        logging.info("Step B: Generating plan based on constraints")
        plan = await call_plan_generator(constraints, tz, requested_days)

        if not plan:
            logging.error("Plan generation failed. Please try again or create plan manually.")
            raise ValueError(
                "Failed to generate workout plan. Please rephrase your request or create a plan manually."
            )

        # Defensive: Strip any IDs the model sneaks in (never trust model-supplied IDs)
        for day in plan.get("days", []):
            for ex in day.get("exercises", []):
                # Never trust model-supplied IDs
                if "exercise_db_id" in ex:
                    logging.info(
                        f"Removing model-supplied exercise_db_id '{ex.get('exercise_db_id')}' for exercise '{ex.get('name', 'Unknown')}'"
                    )
                    ex.pop("exercise_db_id", None)
                # Mark as pending validation
                ex["is_validated"] = False
                ex["validation_confidence"] = "pending"

        # Validate and fix the plan using constraints
        plan = _validate_and_fix_plan(plan, constraints, requested_days)

        # Fill missing or invalid exercise IDs
        plan = _fill_missing_or_invalid_ids(plan)

        # Ensure plan metadata is complete
        plan["program_name"] = plan.get("program_name") or text[:60]
        plan["timezone"] = plan.get("timezone") or tz
        plan["days_per_week"] = len(plan.get("days", []))
        plan["weeks"] = plan.get("weeks") or 1

        # Log the final plan for compliance verification
        logging.info("FINAL PLAN JSON: %s", json.dumps(plan)[:1500])
        logging.info("Final days: %s", [d["weekday"] for d in plan.get("days", [])])
        logging.info(
            "Per-day counts: %s", [len(d.get("exercises", [])) for d in plan.get("days", [])]
        )

        # Validate and enrich exercises with ExerciseDB data
        enriched_data = await validate_and_enrich_exercises(plan)
        return enriched_data

    except Exception as e:
        logging.exception("Schedule generation failed: %s", e)
        raise ValueError(
            "Failed to generate workout plan. Please try again or create a plan manually."
        ) from e
