"""
ExerciseDB client for enriching workout plans with exercise data.
Now uses embedded local JSON data for instant performance and external media URLs.
"""

import json
import logging
from pathlib import Path
from typing import Any


class ExerciseDBClient:
    """Client for interacting with ExerciseDB data (now embedded locally with external media)."""

    def __init__(self):
        # Load exercises data from JSON file
        self.exercises_data = self._load_exercises_data()

    def _load_exercises_data(self) -> list[dict[str, Any]]:
        """Load exercises data from local JSON file."""
        try:
            data_file = Path(__file__).parent / "data" / "exercises.json"
            with open(data_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load exercises data: %s", e)
            return []

    def _load_muscles_data(self) -> list[dict[str, Any]]:
        """Load muscles data from local JSON file."""
        try:
            data_file = Path(__file__).parent / "data" / "muscles.json"
            with open(data_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load muscles data: %s", e)
            return []

    def _load_equipments_data(self) -> list[dict[str, Any]]:
        """Load equipment data from local JSON file."""
        try:
            data_file = Path(__file__).parent / "data" / "equipments.json"
            with open(data_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load equipment data: %s", e)
            return []

    def _load_bodyparts_data(self) -> list[dict[str, Any]]:
        """Load body parts data from local JSON file."""
        try:
            data_file = Path(__file__).parent / "data" / "bodyparts.json"
            with open(data_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load body parts data: %s", e)
            return []

    def get_external_media_url(self, exercise_id: str) -> str | None:
        """Get external media URL for an exercise from ExerciseDB."""
        try:
            # Look up the exercise in our data
            for exercise in self.exercises_data:
                if exercise.get("exerciseId") == exercise_id:
                    # Return the external ExerciseDB media URL
                    return f"https://static.exercisedb.dev/media/{exercise_id}.gif"
            return None
        except Exception as e:
            logging.error("Failed to get external media URL: %s", e)
            return None

    def get_local_gif_path(self, exercise_id: str) -> str | None:
        """Get local path to GIF file for an exercise (DEPRECATED - use get_external_media_url)."""
        logging.warning("get_local_gif_path is deprecated. Use get_external_media_url instead.")
        return self.get_external_media_url(exercise_id)

    def _search_exercises(
        self, query: str, limit: int = 10, exact_match: bool = False
    ) -> list[dict[str, Any]]:
        """Search exercises by name with optional exact matching."""
        if not query:
            return []

        query_lower = query.lower().strip()
        results = []

        for exercise in self.exercises_data:
            exercise_name = exercise.get("name", "").lower().strip()

            if exact_match:
                # Exact match (case-insensitive)
                if query_lower == exercise_name:
                    results.append(exercise)
                    break  # Only one exact match possible
            else:
                # Fuzzy search (substring)
                if query_lower in exercise_name:
                    results.append(exercise)
                    if len(results) >= limit:
                        break

        return results

    def _find_best_match(self, query: str) -> dict[str, Any] | None:
        """Find the best matching exercise using multiple strategies."""
        if not query:
            return None

        query_lower = query.lower().strip()

        # Strategy 1: Exact match
        exact_matches = self._search_exercises(query, exact_match=True)
        if exact_matches:
            return exact_matches[0]

        # Strategy 2: Starts with match (most specific)
        starts_with_matches = []
        for exercise in self.exercises_data:
            exercise_name = exercise.get("name", "").lower().strip()
            if exercise_name.startswith(query_lower):
                starts_with_matches.append(exercise)

        if starts_with_matches:
            # Return the shortest name (most specific match)
            return min(starts_with_matches, key=lambda x: len(x.get("name", "")))

        # Strategy 3: Contains match (least specific)
        contains_matches = []
        for exercise in self.exercises_data:
            exercise_name = exercise.get("name", "").lower().strip()
            if query_lower in exercise_name:
                contains_matches.append(exercise)

        if contains_matches:
            # Return the shortest name (most specific match)
            return min(contains_matches, key=lambda x: len(x.get("name", "")))

        return None

    # Removed search method - no longer needed
    # We now use direct ID lookup instead of name-based search

    # Removed validate_exercise and _calculate_match_quality - no longer needed
    # We now use direct ID lookup instead of name validation

    async def search_exercises_for_user(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search exercises for user interface (manual editing)."""
        try:
            # Use the existing search function
            results = self._search_exercises(query, limit)

            # Transform to user-friendly format
            user_results = []
            for exercise in results:
                exercise_id = exercise.get("exerciseId")
                if exercise_id:
                    user_results.append(
                        {
                            "id": exercise_id,
                            "name": exercise.get("name"),
                            "category": exercise.get("bodyParts", [""])[0]
                            if exercise.get("bodyParts")
                            else "",
                            "equipment": exercise.get("equipments", [""])[0]
                            if exercise.get("equipments")
                            else "",
                            "instructions": exercise.get("instructions", []),
                            "target_muscles": exercise.get("targetMuscles", []),
                            "body_parts": exercise.get("bodyParts", []),
                            "equipments": exercise.get("equipments", []),
                        }
                    )

            return user_results

        except Exception as e:
            logging.error(f"User exercise search failed: {e}")
            return []

    async def search_exercises_by_category(
        self, category: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get exercises by body part category for user selection."""
        try:
            results = []
            for exercise in self.exercises_data:
                body_parts = exercise.get("bodyParts", [])
                if category.lower() in [bp.lower() for bp in body_parts]:
                    exercise_id = exercise.get("exerciseId")
                    if exercise_id:
                        results.append(
                            {
                                "id": exercise_id,
                                "name": exercise.get("name"),
                                "category": body_parts[0] if body_parts else "",
                                "equipment": exercise.get("equipments", [""])[0]
                                if exercise.get("equipments")
                                else "",
                                "instructions": exercise.get("instructions", []),
                            }
                        )
                        if len(results) >= limit:
                            break

            return results

        except Exception as e:
            logging.error(f"Category search failed: {e}")
            return []

    async def search_exercises_by_equipment(
        self, equipment: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get exercises by equipment type for user selection."""
        try:
            results = []
            for exercise in self.exercises_data:
                equipments = exercise.get("equipments", [])
                if equipment.lower() in [eq.lower() for eq in equipments]:
                    exercise_id = exercise.get("exerciseId")
                    if exercise_id:
                        results.append(
                            {
                                "id": exercise_id,
                                "name": exercise.get("name"),
                                "category": exercise.get("bodyParts", [""])[0]
                                if exercise.get("bodyParts")
                                else "",
                                "equipment": equipments[0] if equipments else "",
                                "instructions": exercise.get("instructions", []),
                            }
                        )
                        if len(results) >= limit:
                            break

            return results

        except Exception as e:
            logging.error(f"Equipment search failed: {e}")
            return []

    async def close(self):
        """No need to close anything for local data."""
        pass
