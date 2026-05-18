"""
Telegram Bot — Hand-drawn Animation Agent
==========================================
Run standalone:   python bots/telegram_bot.py

Setup (one time):
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Add TELEGRAM_BOT_TOKEN=<token> to your .env
  3. Add PUBLIC_BASE_URL=https://your-server.com to your .env
     (Volcengine needs a public URL to download the sketch image.
      For local dev: install ngrok and run `ngrok http 8000`, use the https URL.)

Conversation flow:
  /start  → ask user to send image
  📷 image → save file_id, ask for description (and optionally audio)
  🎵 audio → save file_id, ask for description
  💬 text  → run agent, send "⏳ processing...", reply with video URL when done

The Telegram file CDN URL (https://api.telegram.org/file/bot<TOKEN>/<path>)
is publicly reachable, so Volcengine can download images directly from there.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# --- path fix so we can import agent from the project root ---
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv

from agent import run_agent

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

router = Router()


# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------

class AnimState(StatesGroup):
    waiting_image           = State()  # initial — waiting for sketch
    waiting_audio_or_desc   = State()  # got image — audio is optional
    waiting_desc            = State()  # got image + audio — waiting for text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tg_file_url(file_path: str) -> str:
    """Build a public Telegram CDN download URL from a file_path."""
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"


async def _resolve_image_url(bot: Bot, file_id: str) -> str:
    f = await bot.get_file(file_id)
    return _tg_file_url(f.file_path)


async def _resolve_audio_url(bot: Bot, file_id: str) -> str:
    f = await bot.get_file(file_id)
    return _tg_file_url(f.file_path)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AnimState.waiting_image)
    await message.answer(
        "👋 Hi! I'm your Hand-drawn Animation Agent.\n\n"
        "Send me a sketch image (PNG/JPG) and I'll turn it into a video.\n"
        "You can also include an audio file for a talking-head effect.\n\n"
        "Start by sending your sketch image ↓"
    )


@router.message(AnimState.waiting_image, F.photo)
async def handle_image(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]  # largest available size
    await state.update_data(image_file_id=photo.file_id)
    await state.set_state(AnimState.waiting_audio_or_desc)
    await message.answer(
        "✅ Got your sketch!\n\n"
        "Now send me:\n"
        "• A text description of the animation you want\n"
        "• Or send an 🎵 audio/voice file first for a lip-sync effect, then the description"
    )


@router.message(AnimState.waiting_image, ~F.photo)
async def handle_wrong_first_message(message: Message) -> None:
    await message.answer("Please send a sketch image (photo) first.")


@router.message(AnimState.waiting_audio_or_desc, F.audio | F.voice)
async def handle_audio(message: Message, state: FSMContext) -> None:
    audio = message.audio or message.voice
    await state.update_data(audio_file_id=audio.file_id)
    await state.set_state(AnimState.waiting_desc)
    await message.answer("🎵 Got the audio! Now send me a description of the animation.")


@router.message(AnimState.waiting_audio_or_desc | AnimState.waiting_desc, F.text)
async def handle_description(message: Message, state: FSMContext, bot: Bot) -> None:
    data        = await state.get_data()
    description = message.text.strip()

    if not description:
        await message.answer("Please send a non-empty description.")
        return

    await state.clear()
    status_msg = await message.answer(
        "⏳ Got it! Generating your video — this usually takes 1–3 minutes.\n"
        "I'll send the result here when it's ready."
    )

    # Build assets
    assets: dict = {}
    try:
        assets["image_url"] = await _resolve_image_url(bot, data["image_file_id"])
        if audio_id := data.get("audio_file_id"):
            assets["audio_url"] = await _resolve_audio_url(bot, audio_id)

        result = await run_agent(user_request=description, assets=assets)

        if result.error:
            await message.answer(f"❌ Error: {result.error}")
        elif result.video_url:
            plan_summary = " → ".join(s["tool"] for s in result.plan)
            await message.answer(
                f"🎬 Your video is ready!\n\n"
                f"🔗 {result.video_url}\n\n"
                f"Pipeline: {plan_summary}"
            )
        else:
            await message.answer("❌ Agent finished but returned no video URL.")

    except Exception as exc:
        logger.exception("Agent error for user %s", message.from_user.id)
        await message.answer(f"❌ Something went wrong: {exc}")

    finally:
        # Clean up the "processing…" message
        try:
            await bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass

    # Ready for next request
    await state.set_state(AnimState.waiting_image)
    await message.answer("Send another sketch to create a new animation! 🎨")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Telegram bot starting (polling)…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
