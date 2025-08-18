"""
Service for managing workout reminders and scheduling.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class ReminderService:
    """Service for scheduling and managing workout reminders."""

    WEEKDAYS: ClassVar[list[str]] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs_by_chat: dict[int, list[str]] = {}
        self._shutdown_called = False

    async def schedule_plan_reminders(self, bot: Any, chat_id: int, plan: dict[str, Any]) -> None:
        """Schedule reminders for a workout plan."""
        if self._shutdown_called:
            return

        # Start scheduler if not already running
        if not self.scheduler.running:
            self._start_scheduler()

        # Clear existing reminders for this chat
        if chat_id in self.jobs_by_chat:
            for job_id in self.jobs_by_chat[chat_id]:
                try:
                    self.scheduler.remove_job(job_id)  # type: ignore
                except Exception as e:
                    logging.warning("Failed to remove job %s: %s", job_id, e)

        # Schedule new reminders
        new_job_ids: list[str] = []
        for day in plan.get("days", []):
            weekday = day.get("weekday")
            time_str = day.get("time", "19:00")

            if weekday and weekday in self.WEEKDAYS:
                try:
                    # Schedule reminder for next occurrence of this weekday
                    reminder_time = self._next_datetime_for(weekday, time_str, "UTC")
                    if reminder_time:
                        job: Job = self.scheduler.add_job(  # type: ignore
                            self._send_reminder,
                            "date",
                            run_date=reminder_time,
                            args=[bot, chat_id, day],
                            id=f"reminder_{chat_id}_{weekday}_{int(reminder_time.timestamp())}",
                        )
                        new_job_ids.append(job.id)  # type: ignore
                        logging.info(
                            "Scheduled reminder for %s %s at %s", weekday, time_str, reminder_time
                        )
                except Exception as e:
                    logging.exception("Failed to schedule reminder for %s: %s", weekday, e)

        self.jobs_by_chat[chat_id] = new_job_ids

    def _start_scheduler(self) -> None:
        """Start the scheduler."""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logging.info("Reminder scheduler started")
        except Exception as e:
            logging.exception("Failed to start reminder scheduler: %s", e)

    def shutdown(self) -> None:
        """Shutdown the reminder service."""
        if self._shutdown_called:
            return

        self._shutdown_called = True

        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logging.info("Reminder scheduler shutdown")
        except Exception as e:
            logging.exception("Error during reminder scheduler shutdown: %s", e)

    def _next_datetime_for(
        self, weekday: str, time_str: str, tzname: str, weeks_ahead: int = 0
    ) -> datetime | None:
        """Get the next datetime for a given weekday and time."""
        try:
            # Parse time
            hour, minute = map(int, time_str.split(":"))

            # Get current time in target timezone
            tz = ZoneInfo(tzname)
            now = datetime.now(tz)

            # Find target weekday
            target_weekday = self.WEEKDAYS.index(weekday)
            current_weekday = now.weekday()

            # Calculate days until target weekday
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:  # Target weekday has passed this week
                days_ahead += 7

            # Add weeks if specified
            days_ahead += weeks_ahead * 7

            # Create target datetime
            target_date = now.date() + timedelta(days=days_ahead)
            target_datetime = datetime.combine(
                target_date, datetime.min.time().replace(hour=hour, minute=minute)
            )

            return target_datetime.replace(tzinfo=tz)

        except Exception as e:
            logging.exception(
                "Failed to calculate next datetime for %s %s: %s", weekday, time_str, e
            )
            return None

    async def _send_reminder(self, bot: Any, chat_id: int, day_data: dict[str, Any]) -> None:
        """Send a workout reminder."""
        try:
            weekday = day_data.get("weekday", "Today")
            focus = day_data.get("focus", "workout")
            exercises = day_data.get("exercises", [])

            message = f"🏋️ **{weekday} Workout Reminder**\n\n"
            message += f"Focus: {focus}\n\n"
            message += "Today's exercises:\n"

            for exercise in exercises:
                name = exercise.get("name", "Unknown Exercise")  # type: ignore
                sets_data = exercise.get("sets", [])  # type: ignore
                if isinstance(sets_data, list) and sets_data:
                    num_sets = len(sets_data)
                    first_set = sets_data[0]
                    if isinstance(first_set, dict):
                        reps = first_set.get("reps", "?")  # type: ignore
                        message += f"• {name}: {num_sets}x{reps}\n"
                    else:
                        message += f"• {name}: {num_sets} sets\n"
                else:
                    message += f"• {name}\n"

            await bot.send_message(chat_id, message, parse_mode="MarkdownV2")

        except Exception as e:
            logging.exception("Failed to send reminder: %s", e)
