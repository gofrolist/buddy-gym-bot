"""
Tests for logging setup and sensitive data filtering.
"""

import logging

from buddy_gym_bot.logging_setup import SensitiveDataFilter


def test_sensitive_data_filter_telegram_url():
    """Test that Telegram bot tokens are filtered from log messages."""
    filter_obj = SensitiveDataFilter()

    # Create a log record with a sensitive Telegram URL
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage",
        args=(),
        exc_info=None,
    )

    # Apply the filter
    result = filter_obj.filter(record)

    # Check that the filter passed
    assert result is True

    # Check that the sensitive data was redacted
    assert "bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" not in record.msg
    assert "bot<REDACTED>" in record.msg


def test_sensitive_data_filter_openai_url():
    """Test that OpenAI API keys are filtered from log messages."""
    filter_obj = SensitiveDataFilter()

    # Create a log record with a sensitive OpenAI URL
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="https://api.openai.com/v1/chat/completions Bearer sk-1234567890abcdef",
        args=(),
        exc_info=None,
    )

    # Apply the filter
    result = filter_obj.filter(record)

    # Check that the filter passed
    assert result is True

    # Check that the sensitive data was redacted
    assert "sk-1234567890abcdef" not in record.msg
    assert "<REDACTED>" in record.msg


def test_sensitive_data_filter_normal_message():
    """Test that normal messages pass through unchanged."""
    filter_obj = SensitiveDataFilter()

    # Create a log record with a normal message
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="This is a normal log message",
        args=(),
        exc_info=None,
    )

    original_msg = record.msg

    # Apply the filter
    result = filter_obj.filter(record)

    # Check that the filter passed
    assert result is True

    # Check that the message was unchanged
    assert record.msg == original_msg
