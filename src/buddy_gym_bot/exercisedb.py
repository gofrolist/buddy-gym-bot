from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import SETTINGS


class ExerciseDBClient:
    """
    Client for querying the ExerciseDB API, supporting both RapidAPI and direct endpoints.
    """

    def __init__(self) -> None:
        self.base = SETTINGS.EXERCISEDB_BASE_URL
        self.rapid_key = SETTINGS.EXERCISEDB_RAPIDAPI_KEY
        self.rapid_host = SETTINGS.EXERCISEDB_RAPIDAPI_HOST

    def _headers(self) -> dict:
        if self.rapid_key:
            return {"X-RapidAPI-Key": self.rapid_key, "X-RapidAPI-Host": self.rapid_host}
        return {"Accept": "application/json"}

    def _base_url(self) -> str:
        if self.rapid_key:
            return f"https://{self.rapid_host}"
        return self.base

    async def search(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for exercises by name or keyword.
        """
        if not SETTINGS.FF_EXERCISEDB:
            raise RuntimeError("ExerciseDB disabled")
        q = q.strip()
        out: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=10.0, headers=self._headers()) as client:
            # Try generic search
            try:
                url = f"{self._base_url()}/exercises?limit={limit}&search={q}"
                r = await client.get(url)
                if r.status_code == 200:
                    out.extend(r.json())
            except Exception as e:
                logging.warning("ExerciseDB generic search failed: %s", e)
            # Try exact-ish name endpoint
            try:
                url2 = f"{self._base_url()}/exercises/name/{q}"
                r2 = await client.get(url2)
                if r2.status_code == 200:
                    out.extend(r2.json())
            except Exception as e:
                logging.warning("ExerciseDB name search failed: %s", e)
        # Normalize & dedupe
        seen = set()
        normd: list[dict[str, Any]] = []
        for e in out:
            try:
                item = {
                    "id": str(e.get("id") or e.get("_id") or e.get("uuid") or e.get("name")),
                    "name": e.get("name"),
                    "target": e.get("target") or e.get("targetMuscle"),
                    "bodyPart": e.get("bodyPart"),
                    "equipment": e.get("equipment"),
                    "gifUrl": e.get("gifUrl") or e.get("gifURL"),
                }
                key = (item["id"], item["name"])
                if key in seen:
                    continue
                seen.add(key)
                normd.append(item)
            except Exception as e:
                logging.warning("ExerciseDB normalization failed: %s", e)
                continue
        return normd[:limit]

    async def map_plan_exercises(self, plan: dict) -> dict:
        """
        Attach ExerciseDB matches to exercises in a workout plan by name.
        """
        if not SETTINGS.FF_EXERCISEDB:
            return plan
        try:
            for day in plan.get("days", []):
                for ex in day.get("exercises", []):
                    name = ex.get("name")
                    if not name:
                        continue
                    try:
                        matches = await self.search(name, limit=1)
                        if matches:
                            ex["exercisedb"] = matches[0]
                    except Exception as e:
                        logging.warning("ExerciseDB match for '%s' failed: %s", name, e)
            return plan
        except Exception as e:
            logging.warning("ExerciseDB mapping failed: %s", e)
            return plan
