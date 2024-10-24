from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from app.models.schemas import ChatRequest, ChatSummaryRequest
from phi.agent import Agent, RunResponse
from app.core.assistants import (
    get_assistant
)
from app.core.prompts.base import (
    prompt,
    instructions
)
from app.core.prompts.content import (
    reel_script_prompt,
    story_script_prompt,
    general_instruction
)
from app.utils.helpers import chat_response_streamer, is_sensitive_content
from app.core.assistants import storage
import logging
from typing import Optional, List
from app.core.prompts.base import get_summary_prompt_with_context

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat")
async def chat(body: ChatRequest):
    """Sends a message to an Assistant and returns the response"""

    # cancel_flag.clear()

    logger.debug(f"ChatRequest: {body}")

    # Determine session_id based on conditions
    if body.new:
        session_id = None  # New session will be created by the agent
    elif body.session_id:
        session_id = body.session_id  # Use provided session_id
    else:
        # Fetch the latest session_id if neither condition is met
        existing_session_ids: List[str] = storage.get_all_session_ids(body.user_id)
        print(f"existing_session_ids: {existing_session_ids}")
        session_id = existing_session_ids[0] if existing_session_ids else None
    
    agent = (get_assistant(
        session_id=session_id,
        user_id=body.user_id,
        template_category=body.template_category,
        is_speech_to_speech=body.is_speech_to_speech
    ))

    # session_id = agent.session_id
    # print(f"Started Run: {session_id}")
    
    # Comment out after first run
    # agent.knowledge.load(recreate=False)

    extra_prompt = general_instruction

    # Conditionally set extra_prompt based on template_category
    if body.template_category == "REELS_IDEAS":
        extra_prompt = reel_script_prompt()[0]
    elif body.template_category == "STORY_IDEAS":
        extra_prompt = story_script_prompt()[0]

    prompts_first_lines = [
        prompt.split("\n")[0],
        instructions[0],
    ]

    if extra_prompt:
        prompts_first_lines.append(extra_prompt)

    if body.stream:
        return StreamingResponse(
            chat_response_streamer(
                agent, body.message, body.new, prompts_first_lines
            ),
            media_type="text/event-stream",
        )
    else:
        response = agent.run(body.message, stream=False)
        if is_sensitive_content(response, prompts_first_lines):
            response = "Sorry, I'm not able to respond to that request."
        # Only include session_id in response if it's a new session
        return JSONResponse(
            {"session_id": agent.session_id, "response": response} if body.new
            else {"response": response}
        )

@router.post("/chat-summary")
async def chat_summary(body: ChatSummaryRequest):
    """Generates a summary title for the most recent chat message"""
    logger.debug(f"ChatSummaryRequest: {body}")

    agent = (get_assistant(
        session_id=body.session_id,
        user_id=body.user_id
    ))

    summary_prompt_with_context = get_summary_prompt_with_context(body.recent_message)
    response: RunResponse = agent.run(summary_prompt_with_context, stream=False)
    summary = response.content

    return JSONResponse({"response": summary})