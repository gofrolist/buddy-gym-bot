# src/buddy_gym_bot/handlers/ask.py
from aiogram import Router
from aiogram.types import Message
from openai import OpenAI

router = Router()
client = OpenAI()  # reads OPENAI_API_KEY from env

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
        await msg.reply("Usage: /ask Best warm-up for squats?")
        return

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
    except Exception:
        # Keep it user-friendly; log details in real apps
        await msg.reply("Sorry, I couldn't answer that right now. Please try again in a bit.")
