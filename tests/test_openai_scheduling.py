"""
Tests for OpenAI scheduling functionality.
"""

import os
from unittest.mock import patch

from buddy_gym_bot.bot.openai_scheduling import get_openai_vector_store_id


def test_get_openai_vector_store_id_with_env_var():
    """Test getting vector store ID from environment variable."""
    with patch.dict(os.environ, {"OPENAI_VECTOR_STORE_ID": "test_id_123"}):
        result = get_openai_vector_store_id()
        assert result == "test_id_123"


def test_get_openai_vector_store_id_without_env_var():
    """Test getting vector store ID when environment variable is not set."""
    with patch.dict(os.environ, {}, clear=True):
        result = get_openai_vector_store_id()
        assert result is None


def test_get_openai_vector_store_id_empty_env_var():
    """Test getting vector store ID when environment variable is empty."""
    with patch.dict(os.environ, {"OPENAI_VECTOR_STORE_ID": ""}):
        result = get_openai_vector_store_id()
        assert result is None
