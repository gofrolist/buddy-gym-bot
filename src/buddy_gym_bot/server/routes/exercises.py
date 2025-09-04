"""
Exercise search API route for BuddyGym.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from ...config import SETTINGS
from ...exercisedb import ExerciseDBClient

router = APIRouter()


@router.get("/exercises/categories")
async def exercises_categories() -> dict:
    """
    List available exercise body part categories.

    This powers the UI category filter without hardcoding.
    """
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")

    client = ExerciseDBClient()
    try:
        # Leverage the local bodyparts data from ExerciseDBClient
        # It provides human-readable body part names.
        categories = [
            (bp.get("name") or "").strip()
            for bp in client._load_bodyparts_data()
            if (bp.get("name") or "").strip()
        ]
        # Normalize to lowercase URL-friendly values for API usage
        normalized = sorted({c.lower() for c in categories})
    except Exception as err:
        logging.exception("Failed to load exercise categories")
        raise HTTPException(status_code=500, detail="Failed to load categories") from err
    finally:
        await client.close()

    return {"ok": True, "items": normalized, "total": len(normalized)}


@router.get("/exercises/search")
async def exercises_search(
    q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)
) -> dict:
    """
    Search for exercises using ExerciseDB. Returns a list of matching exercises.
    Perfect for manual plan editing where users type exercise names.
    """
    # Feature flag: ExerciseDB must be enabled
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")

    client = ExerciseDBClient()
    try:
        items = await client.search_exercises_for_user(q, limit=limit)
    except Exception as err:
        logging.exception("ExerciseDB search failed")
        # mask remote errors
        raise HTTPException(status_code=502, detail="Upstream error") from err
    finally:
        await client.close()

    return {"ok": True, "items": items, "query": q, "total": len(items)}


@router.get("/exercises/{exercise_id}")
async def exercise_by_id(exercise_id: str) -> dict:
    """
    Fetch a single exercise by its ExerciseDB ID.

    UI should prefer this endpoint when an exercise_db_id is available from the plan.
    """
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")

    client = ExerciseDBClient()
    try:
        for exercise in client.exercises_data:
            if exercise.get("exerciseId") == exercise_id:
                body_parts = exercise.get("bodyParts", [])
                equipments = exercise.get("equipments", [])
                return {
                    "ok": True,
                    "item": {
                        "id": exercise_id,
                        "name": exercise.get("name"),
                        "category": body_parts[0] if body_parts else "",
                        "equipment": equipments[0] if equipments else "",
                        "instructions": exercise.get("instructions", []),
                        "target_muscles": exercise.get("targetMuscles", []),
                        "body_parts": body_parts,
                        "equipments": equipments,
                        "image": client.get_external_media_url(exercise_id),
                    },
                }
        raise HTTPException(status_code=404, detail="Exercise not found")
    finally:
        await client.close()


@router.get("/exercises/category/{category}")
async def exercises_by_category(category: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    """
    Get exercises by body part category (e.g., chest, back, legs).
    Useful for browsing exercises by muscle group.
    """
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")

    client = ExerciseDBClient()
    try:
        items = await client.search_exercises_by_category(category, limit=limit)
    except Exception as err:
        logging.exception("ExerciseDB category search failed")
        raise HTTPException(status_code=502, detail="Upstream error") from err
    finally:
        await client.close()

    return {"ok": True, "items": items, "category": category, "total": len(items)}


@router.get("/exercises/equipment/{equipment}")
async def exercises_by_equipment(equipment: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    """
    Get exercises by equipment type (e.g., barbell, dumbbell, bodyweight).
    Useful for filtering exercises by available equipment.
    """
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")

    client = ExerciseDBClient()
    try:
        items = await client.search_exercises_by_equipment(equipment, limit=limit)
    except Exception as err:
        logging.exception("ExerciseDB equipment search failed")
        raise HTTPException(status_code=502, detail="Upstream error") from err
    finally:
        await client.close()

    return {"ok": True, "items": items, "equipment": equipment, "total": len(items)}
