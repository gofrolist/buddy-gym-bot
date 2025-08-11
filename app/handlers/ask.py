from aiogram import Router
from aiogram.types import Message
from openai import OpenAI
from ..settings import settings

router = Router()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYS = "You are a concise, evidence-informed strength coach. Give clear, safe, actionable advice in 4-6 bullet points max. No medical advice."

@router.message(lambda m: m.text and m.text.startswith("/ask"))
async def ask(msg: Message):
    q = msg.text[len("/ask"):].strip()
    if not q:
        return await msg.reply("Usage: /ask Best warm-up for squats?")
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":SYS},{"role":"user","content":q}],
        temperature=0.3,
    )
    await msg.reply(r.choices[0].message.content.strip())