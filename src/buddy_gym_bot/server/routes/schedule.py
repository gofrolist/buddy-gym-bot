"""
Schedule API endpoints for workout plan modifications and trainer communication.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...db import repo
from ...services.openai_service import OpenAIService

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
        # Ensure user exists
        await repo.upsert_user(request.tg_user_id, handle=None, lang=None)

        logging.info(f"Schedule request from user {request.tg_user_id}: {request.message}")
        logging.info(f"Context provided: {bool(request.context)}")

        # Initialize OpenAI service
        openai_service = OpenAIService()

        # Build comprehensive prompt for AI
        ai_prompt = f"""You are an experienced fitness trainer and workout plan specialist. A user has sent you the following request about their workout plan:

USER REQUEST: "{request.message}"

CURRENT CONTEXT:
"""

        # Add context if available
        if request.context:
            if request.context.get('current_plan'):
                plan = request.context['current_plan']
                ai_prompt += f"""
Current Workout Plan: {plan.get('program_name', 'Unnamed Plan')}
- Duration: {plan.get('weeks', 'Unknown')} weeks
- Frequency: {plan.get('days_per_week', 'Unknown')} days per week
- Days scheduled: {len(plan.get('days', []))} days
"""

                # Add details about workout days
                if plan.get('days'):
                    ai_prompt += "\nWorkout Schedule:\n"
                    for day in plan['days']:
                        ai_prompt += f"- {day.get('weekday', 'Unknown')}: {day.get('focus', 'No focus specified')} ({day.get('time', 'No time set')})\n"
                        if day.get('exercises'):
                            ai_prompt += f"  Exercises: {len(day['exercises'])} exercises planned\n"

            if request.context.get('workout_history'):
                history = request.context['workout_history']
                if history:
                    ai_prompt += f"\nRecent Workout History: {len(history)} recent sessions"

            if request.context.get('current_workout'):
                current = request.context['current_workout']
                if current.get('active'):
                    ai_prompt += f"\nCurrent Workout: Active session with {len(current.get('sets', []))} sets completed"

        ai_prompt += """

Please provide a helpful, professional response as a fitness trainer. Consider:
1. The user's specific request and needs
2. Their current plan and progress
3. Safety and proper progression principles
4. Practical and actionable advice

Be supportive, knowledgeable, and provide specific recommendations where appropriate. Keep your response conversational but professional, as if you're speaking directly to your client. Limit your response to 2-3 paragraphs maximum.
"""

        # Get AI response
        if openai_service.is_available():
            logging.info("Sending request to OpenAI for schedule advice")
            ai_response = await openai_service.get_completion(ai_prompt, max_tokens=400)

            if ai_response:
                logging.info(f"OpenAI response received: {len(ai_response)} characters")

                return ScheduleResponse(
                    success=True,
                    message="Schedule request processed successfully with AI assistance",
                    response=ai_response,
                    plan=None,  # TODO: Implement plan modifications based on AI suggestions
                )
            else:
                logging.warning("OpenAI service returned no response, using fallback")
        else:
            logging.info("OpenAI service not available, using fallback response")

        # Fallback to pattern-based responses if AI is unavailable
        message_lower = request.message.lower()

        # Generate contextual response based on request content
        if any(word in message_lower for word in ["add", "more", "increase"]):
            response_message = "I'll review your request to add more exercises or increase intensity. This is a great way to challenge yourself! I'll get back to you with an updated plan within 24 hours."
        elif any(
            word in message_lower for word in ["reduce", "less", "tired", "fatigue", "recovery"]
        ):
            response_message = "I understand you're feeling fatigued. Recovery is crucial for progress! I'll adjust your plan to include more rest and reduce volume. You should see the changes in your plan shortly."
        elif any(word in message_lower for word in ["change", "replace", "substitute"]):
            response_message = "I'll work on finding suitable exercise substitutions for you. Everyone's body is different, so let's find what works best for your situation."
        elif any(word in message_lower for word in ["time", "schedule", "day"]):
            response_message = "I'll help you adjust the timing and scheduling of your workouts to better fit your lifestyle. Consistency is key!"
        elif any(word in message_lower for word in ["strength", "power", "heavy"]):
            response_message = "Focusing on strength training is excellent! I'll modify your plan to emphasize heavier loads and lower rep ranges to help you build maximum strength."
        elif any(word in message_lower for word in ["cardio", "endurance", "conditioning"]):
            response_message = "Great focus on cardiovascular fitness! I'll incorporate more conditioning work and adjust rest periods to improve your endurance."
        else:
            response_message = "Thanks for your feedback! I'll review your request and current progress to make the best adjustments to your plan. Expect updates within 24 hours."

        return ScheduleResponse(
            success=True,
            message="Schedule request received successfully",
            response=response_message,
            plan=None,  # Would return updated plan if immediately modified
        )

    except Exception as e:
        logging.exception(f"Error processing schedule request: {e}")
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
