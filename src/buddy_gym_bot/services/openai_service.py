"""
Service for OpenAI API interactions.
"""

import logging

import httpx

from ..config import SETTINGS


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        self.api_key = SETTINGS.OPENAI_API_KEY
        self.base_url = "https://api.openai.com/v1"
        self.default_model = "gpt-5-mini"
        self.default_timeout = 20.0

    async def get_completion(
        self, prompt: str, max_tokens: int = 500, model: str | None = None
    ) -> str | None:
        """
        Get a completion from OpenAI API.

        Args:
            prompt: User's question or prompt
            max_tokens: Maximum tokens for response
            model: OpenAI model to use (defaults to gpt-4o-mini)

        Returns:
            AI-generated response or None if failed
        """
        if not self.api_key:
            logging.info("OpenAI API key not configured")
            return None

        if not prompt.strip():
            logging.warning("Empty prompt provided to OpenAI service")
            return None

        model = model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=self.default_timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()

                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
                    logging.info(f"OpenAI response received: {len(content)} characters")
                    return content
                else:
                    logging.warning("Unexpected OpenAI response format")
                    return None

        except httpx.HTTPError as e:
            logging.warning("OpenAI HTTP request failed: %s", e)
            return None
        except Exception as e:
            logging.exception("Unexpected error in OpenAI service: %s", e)
            return None

    async def get_fitness_advice(self, question: str) -> str:
        """
        Get fitness advice using OpenAI.

        Args:
            question: User's fitness question

        Returns:
            AI-generated fitness advice or fallback response
        """
        # Try to get AI response
        ai_response = await self.get_completion(question)

        if ai_response:
            # Truncate if too long
            if len(ai_response) > 500:
                ai_response = ai_response[:500] + "..."
            return ai_response

        # Fallback response if AI is unavailable
        return (
            "My quick take: stay consistent, use good form, progressive overload. "
            "For specific advice, consider consulting a certified personal trainer."
        )

    def is_available(self) -> bool:
        """Check if OpenAI service is available."""
        return bool(self.api_key)
