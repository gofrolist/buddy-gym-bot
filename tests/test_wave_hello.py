from buddy_gym_bot.bot.utils import wave_hello


def test_wave_hello_contains_emoji():
    message = wave_hello("Alex")
    assert "👋" in message
    assert "Alex" in message
