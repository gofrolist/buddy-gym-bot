from buddy_gym_bot.progression import next_load, should_deload


def test_progression_up():
    assert next_load(60, True, 5) == 62.5


def test_progression_repeat():
    assert next_load(60, False, 8) == 60


def test_deload_rule():
    assert not should_deload(1)
    assert should_deload(2)
