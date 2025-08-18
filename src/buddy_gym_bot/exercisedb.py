"""
ExerciseDB client for enriching workout plans with exercise data.
"""

import logging
from typing import Any

import httpx


class ExerciseDBClient:
    """Client for interacting with the ExerciseDB API."""

    def __init__(self):
        # Updated base URL to use www subdomain to avoid redirects
        self.base_url = "https://www.exercisedb.dev/api/v1"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,  # Enable redirect following
        )

    def _headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {"Accept": "application/json", "User-Agent": "GymBuddyBot/1.0"}

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for exercises by name."""
        try:
            url = f"{self.base_url}/exercises"
            params = {"name": query, "limit": limit}

            response = await self.client.get(url, params=params, headers=self._headers())
            response.raise_for_status()

            data = response.json()
            return data.get("data", [])

        except httpx.HTTPStatusError as e:
            logging.error("Exercise search failed: %s", e)
            return []
        except Exception as e:
            logging.exception("Unexpected error during exercise search: %s", e)
            return []

    async def map_plan_exercises(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Map exercise names in a workout plan to ExerciseDB data."""
        if "exercises" not in plan:
            return plan

        mapped_exercises: list[dict[str, Any]] = []
        for exercise in plan["exercises"]:
            if isinstance(exercise, dict) and "name" in exercise:
                exercise_name = exercise["name"]
                # Search for the exercise
                search_results = await self.search(exercise_name, limit=1)

                if search_results:
                    # Use the first result
                    db_exercise = search_results[0]
                    mapped_exercise = {
                        **exercise,
                        "exercise_db_id": db_exercise.get("id"),
                        "exercise_db_name": db_exercise.get("name"),
                        "exercise_db_category": db_exercise.get("category"),
                        "exercise_db_equipment": db_exercise.get("equipment"),
                        "exercise_db_instructions": db_exercise.get("instructions"),
                    }
                else:
                    # Keep original exercise data if not found
                    mapped_exercise = exercise

                mapped_exercises.append(mapped_exercise)
            else:
                mapped_exercises.append(exercise)

        return {**plan, "exercises": mapped_exercises}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
