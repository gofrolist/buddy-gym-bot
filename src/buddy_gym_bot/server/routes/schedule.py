"""
Schedule API endpoints for workout plan modifications and trainer communication.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...bot.openai_scheduling import generate_schedule
from ...config import SETTINGS
from ...db import repo

router = APIRouter()


class ScheduleRequest(BaseModel):
    """Request model for schedule modifications."""

    tg_user_id: int = Field(..., description="Telegram user ID")
    message: str = Field(..., description="User's request message")
    context: dict[str, Any] | None = Field(None, description="Current workout context")


class ScheduleResponse(BaseModel):
    """Response model for schedule requests."""

    success: bool = Field(default=True)
    message: str = Field(..., description="Response message")
    response: str = Field(..., description="Trainer/system response")
    plan: dict[str, Any] | None = Field(None, description="Updated plan if modified")


@router.post("/schedule", response_model=ScheduleResponse)
async def request_schedule_change(request: ScheduleRequest):
    """
    Handle schedule change requests from users using OpenAI for intelligent responses.

    This endpoint allows users to request modifications to their workout plan
    by sending a message to their trainer or the system, powered by AI.
    """
    try:
        logging.info("=== SCHEDULE REQUEST START ===")
        logging.info(
            f"Request received: tg_user_id={request.tg_user_id}, message='{request.message}'"
        )
        logging.info(f"Request context: {request.context}")

        # Log environment variables
        logging.info(f"OPENAI_API_KEY configured: {bool(SETTINGS.OPENAI_API_KEY)}")
        logging.info(
            f"OPENAI_API_KEY length: {len(SETTINGS.OPENAI_API_KEY) if SETTINGS.OPENAI_API_KEY else 0}"
        )

        # Ensure user exists
        logging.info(f"Upserting user with tg_user_id: {request.tg_user_id}")
        await repo.upsert_user(request.tg_user_id, handle=None, lang=None)
        logging.info("User upserted successfully")

        logging.info(f"Schedule request from user {request.tg_user_id}: {request.message}")
        logging.info(f"Context provided: {bool(request.context)}")
        if request.context:
            logging.info(f"Context details: {json.dumps(request.context, default=str)}")

        # Ensure user exists first (this is critical for foreign key constraints)
        try:
            user = await repo.upsert_user(request.tg_user_id, handle=None, lang=None)
            logging.info(
                f"Ensured user {request.tg_user_id} exists in database with internal ID {user.id}"
            )
        except Exception as e:
            logging.error(f"Failed to ensure user exists: {e}")
            return ScheduleResponse(
                success=False,
                message="Failed to process schedule request",
                response="I'm sorry, there was an issue with your user account. Please try again or contact support.",
                plan=None,
            )

        # Get current plan for context
        current_plan = None
        if request.context and request.context.get("current_plan"):
            # Reconstruct the full plan structure from the simplified context
            try:
                user_plan = await repo.get_user_plan(user.id)
                if user_plan and user_plan.get("days"):
                    current_plan = user_plan
                    logging.info(
                        f"Using existing plan with {len(user_plan['days'])} days for context"
                    )
            except Exception as e:
                logging.warning(f"Failed to fetch current plan for context: {e}")

        # Generate schedule using the same logic as Telegram bot
        logging.info("=== OPENAI SCHEDULE GENERATION START ===")
        logging.info("Generating schedule using OpenAI scheduling service")
        try:
            # Check if OpenAI API key is available
            logging.info("Checking OpenAI API key...")
            if not SETTINGS.OPENAI_API_KEY:
                logging.warning("OpenAI API key not configured, using fallback response")
                raise ValueError("OpenAI API key not configured for local development")

            logging.info(f"OpenAI API key is configured, length: {len(SETTINGS.OPENAI_API_KEY)}")
            logging.info("About to call generate_schedule...")
            logging.info(
                f"generate_schedule parameters: text='{request.message}', tz='UTC', base_plan={bool(current_plan)}"
            )

            new_plan = await generate_schedule(
                text=request.message,
                tz="UTC",  # TODO: Get user's timezone from context
                base_plan=current_plan,
            )
            logging.info("generate_schedule completed successfully")
            logging.info(f"Generated plan type: {type(new_plan)}")
            logging.info(f"Generated plan keys: {list(new_plan.keys()) if new_plan else 'None'}")

            logging.info(
                f"Generated plan: {json.dumps(new_plan, indent=2) if new_plan else 'None'}"
            )
            logging.info(
                f"Current plan: {json.dumps(current_plan, indent=2) if current_plan else 'None'}"
            )

            if new_plan:
                # Always save and return the new plan if it was generated
                logging.info(f"Generated new plan: {new_plan.get('program_name', 'Unknown')}")

                # Save the new plan to database
                try:
                    await repo.upsert_user_plan(user.id, new_plan)
                    logging.info(
                        f"Successfully saved new plan for user {request.tg_user_id} (internal ID: {user.id})"
                    )
                except Exception as e:
                    logging.error(f"Failed to save new plan to database: {e}")
                    return ScheduleResponse(
                        success=False,
                        message="Failed to save updated plan",
                        response=f"I generated a new workout plan based on your request: '{request.message}', but there was an issue saving it to your account. Please try again or contact support.",
                        plan=new_plan,  # Still return the plan so user can see what was generated
                    )

                return ScheduleResponse(
                    success=True,
                    message="Schedule updated successfully with AI assistance",
                    response=f"I've updated your workout plan based on your request: '{request.message}'. The new plan '{new_plan.get('program_name', 'Updated Plan')}' has been generated and is ready for you.",
                    plan=new_plan,
                )
            else:
                logging.error("AI did not return a plan")
                return ScheduleResponse(
                    success=False,
                    message="Failed to generate workout plan",
                    response=(
                        "OpenAI couldn't generate a plan right now. Please create a plan manually or try again later."
                    ),
                    plan=None,
                )

        except Exception as e:
            logging.error("=== OPENAI SCHEDULE GENERATION FAILED ===")
            logging.exception(f"Failed to generate schedule: {e}")
            logging.error(f"Exception type: {type(e).__name__}")
            logging.error(f"Exception details: {e!s}")
            logging.error(f"Exception traceback: {e.__traceback__}")
            return ScheduleResponse(
                success=False,
                message="Failed to generate workout plan",
                response=(
                    "OpenAI couldn't generate a plan right now. Please create a plan manually or try again later."
                ),
                plan=None,
            )

    except Exception as e:
        logging.error("=== SCHEDULE REQUEST FAILED ===")
        logging.exception(f"Error processing schedule request: {e}")
        logging.error(f"Exception type: {type(e).__name__}")
        logging.error(f"Exception details: {e!s}")
        return ScheduleResponse(
            success=False,
            message="Failed to process schedule request",
            response="I'm sorry, there was an issue processing your request. Please try again or contact support if the problem persists.",
            plan=None,
        )


@router.get("/schedule/history", response_model=list[dict[str, Any]])
async def get_schedule_history(tg_user_id: int = Query(..., description="Telegram user ID")):
    """
    Get the history of schedule requests for a user.

    This would return previous conversations between the user and trainer.
    """
    try:
        # Ensure user exists
        await repo.upsert_user(tg_user_id, handle=None, lang=None)

        # For now, return empty history
        # In a real implementation, this would fetch from database:
        # history = await repo.get_schedule_history(tg_user_id)

        logging.info(f"Schedule history requested for user {tg_user_id}")

        return []

    except Exception as e:
        logging.exception(f"Error fetching schedule history: {e}")
        return []
