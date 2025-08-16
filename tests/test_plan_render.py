from buddy_gym_bot.bot.main import render_plan_message


def test_render_plan_message():
    plan = {
        "days": [
            {
                "weekday": "Mon",
                "time": "18:00",
                "focus": "Upper",
                "exercises": [
                    {"name": "Bench", "sets": [{"reps": "3x5"}]},
                    {"name": "Row", "sets": [{"reps": "3x8"}]},
                ],
            },
            {
                "weekday": "Wed",
                "time": "18:00",
                "focus": "Lower",
                "exercises": [{"name": "Squat", "sets": [{"reps": "3x5"}]}],
            },
        ]
    }
    text = render_plan_message(plan)
    assert "Mon 18:00 — Upper" in text
    assert "• Bench: 3x5" in text
    assert "Wed 18:00 — Lower" in text
    assert "• Squat: 3x5" in text
