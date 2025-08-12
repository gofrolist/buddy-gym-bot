"""Handler for the /ask command."""

import logging

from aiogram import Router
from aiogram.types import Message
from openai import APIConnectionError, APIError, OpenAIError, RateLimitError

from buddy_gym_bot.handlers.alerts import alert_admin
from buddy_gym_bot.settings import get_openai_client

router = Router()
client = get_openai_client()

logger = logging.getLogger(__name__)

SYS: str = (
    "You are a concise, evidence-informed strength coach. "
    "Give clear, safe, actionable advice in 4-6 bullet points max. "
    "No medical advice."
)


@router.message(lambda m: (m.text or "").startswith("/ask"))
async def ask(msg: Message) -> None:
    # text can be None at type-check time; guard it
    text: str = msg.text or ""
    query: str = text[len("/ask") :].strip()
    if not query:
        logger.debug("Empty /ask query from %s", getattr(msg.from_user, "id", "unknown"))
        await msg.reply("Usage: /ask Best warm-up for squats?")
        return
    logger.info("/ask from %s: %s", getattr(msg.from_user, "id", "unknown"), query)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYS},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
        )
        content = resp.choices[0].message.content or ""
        # Ensure we send back a string
        if not isinstance(content, str):
            content = str(content)
        await msg.reply(content.strip())
    except RateLimitError as exc:
        logger.exception("OpenAI rate limit on /ask: %s", exc)
        if getattr(exc, "code", "") == "insufficient_quota" and msg.bot is not None:
            await alert_admin(msg.bot, "OpenAI quota exhausted during /ask")
        await msg.reply("I'm getting a lot of questions right now. Please try again later.")
    except APIConnectionError as exc:
        logger.exception("OpenAI connection error on /ask: %s", exc)
        await msg.reply("I couldn't reach the AI service. Please try again later.")
    except APIError as exc:
        logger.exception("OpenAI API error on /ask: %s", exc)
        await msg.reply("The AI service returned an error. Please try again later.")
    except OpenAIError as exc:
        logger.exception("OpenAI error on /ask: %s", exc)
        await msg.reply("Sorry, I couldn't get an answer from the AI service.")
    except Exception as exc:
        logger.exception("Failed to answer /ask: %s", exc)
        await msg.reply("Sorry, I couldn't answer that right now. Please try again in a bit.")
