from dataclasses import dataclass
from typing import List, Dict

@dataclass
class UserProfile:
    goal: str          # strength, hypertrophy, fat_loss, general
    experience: str    # novice, intermediate, advanced
    days_per_week: int
    equipment: str     # gym, dumbbells, bodyweight

FULL_BODY = [
  {"name":"Squat", "sets":3, "reps":5},
  {"name":"Bench Press", "sets":3, "reps":5},
  {"name":"Row", "sets":3, "reps":8},
  {"name":"Overhead Press", "sets":2, "reps":8},
  {"name":"RDL", "sets":2, "reps":8},
  {"name":"Plank", "sets":3, "reps":45},
]

def make_week_plan(u: UserProfile) -> List[List[Dict]]:
    days = max(3, min(6, u.days_per_week or 3))
    week: List[List[Dict]] = []
    for d in range(days):
        day = list(FULL_BODY)
        if d % 2 == 1:
            day = day[1:] + day[:1]
        week.append(day)
    return week