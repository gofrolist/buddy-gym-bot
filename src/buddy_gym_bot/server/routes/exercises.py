"""
Exercise search API route for BuddyGym.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from ...config import SETTINGS
from ...exercisedb import ExerciseDBClient

router = APIRouter()


@router.get("/exercises/search")
async def exercises_search(q: str = Query(..., min_length=1), limit: int = 10) -> dict:
    """
    Search for exercises using ExerciseDB. Returns a list of matching exercises.
    """
    # Feature flag: ExerciseDB must be enabled
    if not SETTINGS.FF_EXERCISEDB:
        raise HTTPException(status_code=503, detail="ExerciseDB disabled")
    client = ExerciseDBClient()
    try:
        items = await client.search(q, limit=limit)
    except Exception:
        logging.exception("ExerciseDB search failed")
        # mask remote errors
        raise HTTPException(status_code=502, detail="Upstream error")
    return {"ok": True, "items": items}
