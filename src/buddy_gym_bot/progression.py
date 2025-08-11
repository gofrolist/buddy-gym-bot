def next_load(current_weight: float | None, success: bool, rep_goal: int) -> float:
    if current_weight is None:
        return 20.0
    if success:
        jump = 2.5 if rep_goal <= 6 else 2.0
        return round(current_weight + jump, 1)
    return current_weight


def should_deload(fails_in_row: int) -> bool:
    return fails_in_row >= 2
