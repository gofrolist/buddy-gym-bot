"""
Main bot module with command handlers and bot initialization.
Refactored to use service layer and improve code organization.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..config import SETTINGS
from ..logging_setup import setup_logging
from ..services import OpenAIService, ReminderService, WorkoutService
from .command_utils import (
    ensure_user_exists,
    extract_command_args,
    handle_referral_click,
    handle_referral_fulfillment,
    validate_positive_number,
)
from .commands_labels import apply_localized_commands
from .parsers import TRACK_RE
from .utils import wave_hello, webapp_button

# Initialize router and services
router = Router()
workout_service = WorkoutService()
openai_service = OpenAIService()
reminder_service = ReminderService()


@router.message(CommandStart(deep_link=True))
async def cmd_start_dl(message: Message) -> None:
    """Handle /start with deep link."""
    await _handle_start(message)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await _handle_start(message)


async def _handle_start(message: Message) -> None:
    """Handle start command and referral processing."""
    try:
        # Ensure user exists in database
        user = await ensure_user_exists(message)
        if not user:
            await message.answer("Sorry, I couldn't set up your account. Please try again.")
            return

        # Handle referral if present
        await handle_referral_click(message)

        # Send welcome message with webapp button
        kb = webapp_button(SETTINGS.WEBAPP_URL, "Open BuddyGym")
        greeting = wave_hello(
            message.from_user.first_name or "Athlete" if message.from_user else "Athlete"
        )
        await message.answer(
            f"{greeting} Welcome to BuddyGym! Track your workouts and get reminders.",
            reply_markup=kb,
        )

    except Exception as e:
        logging.exception("Start command failed: %s", e)
        await message.answer(
            "Welcome to BuddyGym! Something went wrong, but you can still use the bot."
        )


@router.message(Command("track"))
async def cmd_track(message: Message) -> None:
    """Handle /track command for logging a workout set."""
    start_time = asyncio.get_event_loop().time()

    try:
        # Extract and validate command arguments
        args = extract_command_args(message, "/track")
        if not args:
            await _send_track_usage(message)
            return

        # Parse exercise data using regex
        match = TRACK_RE.match(args)
        if not match:
            await _send_track_usage(message)
            return

        # Extract and validate data
        exercise = match.group("ex")
        weight_str = match.group("w")
        reps_str = match.group("r")
        rpe_str = match.group("rpe")

        # Validate weight
        weight_valid, weight, weight_error = validate_positive_number(weight_str, "Weight")
        if not weight_valid or weight is None:
            await message.reply(weight_error)
            return

        # Validate reps
        reps_valid, reps, reps_error = validate_positive_number(reps_str, "Reps")
        if not reps_valid or reps is None:
            await message.reply(reps_error)
            return

        # Parse RPE if present
        rpe = None
        if rpe_str:
            try:
                rpe = float(rpe_str)
                if not (1 <= rpe <= 10):
                    await message.reply("RPE must be between 1 and 10.")
                    return
            except ValueError:
                await message.reply("RPE must be a valid number.")
                return

        # Ensure user exists
        user = await ensure_user_exists(message)
        if not user:
            await message.answer("Sorry, I couldn't access your account. Please try again.")
            return

        # Log the workout set (this should be fast)
        result = await workout_service.log_workout_set(
            user.id, exercise, weight, int(reps), rpe, is_warmup=False
        )

        if "error" in result:
            await message.answer(f"Error logging set: {result['error']}")
            return

        # Send confirmation immediately
        rpe_text = f" RPE{rpe:g}" if rpe else ""
        await message.answer(f"Logged: {exercise} {weight}x{reps}{rpe_text}")

        # Handle referral fulfillment asynchronously (non-blocking)
        _referral_task = asyncio.create_task(handle_referral_fulfillment(user.id, message))  # noqa: RUF006

        # Log performance
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        logging.info("Track command completed in %.1fms", elapsed)

    except Exception as e:
        logging.exception("Track command failed: %s", e)
        await message.answer("Sorry, I couldn't log your set. Please try again.")


async def _send_track_usage(message: Message) -> None:
    """Send track command usage instructions."""
    usage_text = "Usage: /track (exercise) (weight)x(reps) [rpeX]\nExample: /track bench 100x5 rpe8"
    await message.reply(usage_text)


@router.message(Command("schedule"))
async def cmd_schedule(message: Message) -> None:
    """Handle /schedule command to generate or modify a workout plan."""
    try:
        # Ensure user exists
        user = await ensure_user_exists(message)
        if not user:
            await message.answer("Sorry, I couldn't access your account. Please try again.")
            return

        # Extract request text
        request_text = extract_command_args(message, "/schedule")
        timezone = getattr(user, "tz", None) or "UTC"

        # Create or modify workout plan
        plan = await workout_service.create_workout_plan(user.id, request_text, timezone)

        # Schedule reminders if enabled
        if SETTINGS.FF_REMINDERS:
            try:
                bot = message.bot
                if bot is None:
                    raise RuntimeError("Bot instance is unavailable")
                await reminder_service.schedule_plan_reminders(bot, message.chat.id, plan)  # type: ignore
            except Exception as e:
                logging.exception("Failed to schedule reminders: %s", e)
                # Don't fail the command if reminders fail

        # Send plan summary
        plan_message = workout_service.render_plan_message(plan)
        await message.answer(plan_message)

    except Exception as e:
        logging.exception("Schedule command failed: %s", e)
        await message.answer("Sorry, I couldn't create your workout plan. Please try again.")


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    """Handle /today command."""
    try:
        # TODO: Implement actual today's workout logic
        await message.answer(
            "Today: 3 sets x 5 reps of a compound lift + accessories. Go crush it! 💪"
        )
    except Exception as e:
        logging.exception("Today command failed: %s", e)
        await message.answer("Sorry, I couldn't get today's workout. Please try again.")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Handle /stats command."""
    try:
        # TODO: Implement actual stats logic
        await message.answer("Stats (stub): 5 workouts this week, 12,300 kg total volume.")
    except Exception as e:
        logging.exception("Stats command failed: %s", e)
        await message.answer("Sorry, I couldn't get your stats. Please try again.")


@router.message(Command("ask"))
async def cmd_ask(message: Message) -> None:
    """Handle /ask command to answer user questions using OpenAI if available."""
    try:
        # Extract question
        question = extract_command_args(message, "/ask")
        if not question:
            await message.reply("Ask me something like: /ask How to fix my squat form?")
            return

        # Get AI-powered fitness advice
        answer = await openai_service.get_fitness_advice(question)
        await message.answer(answer)

    except Exception as e:
        logging.exception("Ask command failed: %s", e)
        await message.answer("Sorry, I had an error answering that. Please try again.")


async def on_startup(bot: Bot) -> None:
    """Startup routine: set up logging, initialize DB, and apply localized commands."""
    try:
        setup_logging()
        from ..db import repo

        # Delete any existing webhook if running in polling mode
        if not SETTINGS.USE_WEBHOOK:
            try:
                await bot.delete_webhook()
                logging.info("Deleted existing webhook for polling mode")
            except Exception as e:
                logging.warning("Failed to delete webhook: %s", e)

        await repo.init_db()
        await apply_localized_commands(bot)
        logging.info("Bot startup completed successfully")
    except Exception as e:
        logging.exception("Bot startup failed: %s", e)
        raise


async def on_shutdown(bot: Bot) -> None:
    """Shutdown routine: clean up resources."""
    try:
        reminder_service.shutdown()
        logging.info("Bot shutdown completed successfully")
    except Exception as e:
        logging.exception("Bot shutdown failed: %s", e)
    finally:
        # Ensure we don't try to shutdown again
        pass


def create_dispatcher(bot: Bot) -> Dispatcher:
    """Create dispatcher with all routers and startup/shutdown handlers."""
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return dp


async def _run() -> None:
    """Main bot run function."""
    if SETTINGS.USE_WEBHOOK:
        raise SystemExit("USE_WEBHOOK is enabled; polling is disabled")
    if not SETTINGS.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is required")

    bot = Bot(SETTINGS.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(bot)

    try:
        await dp.start_polling(bot)  # type: ignore
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.exception("Bot polling failed: %s", e)
        raise
    finally:
        await on_shutdown(bot)


def main() -> None:
    """Main entry point."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
