from fastapi import APIRouter, Request, BackgroundTasks
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
from app.core.security import auth_middleware

from app.services.token_usage_tracker import TokenUsageTracker

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat")
@auth_middleware.requires_auth
async def chat(request: Request, body: ChatRequest):
    """Sends a message to an Assistant and returns the response"""

    # cancel_flag.clear()

    logger.debug(f"ChatRequest: {body}")
    print(f"request: {request}")

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

    token_tracker = TokenUsageTracker()

    if body.stream:
        # For streaming responses, update tokens after stream ends
        response_generator = chat_response_streamer(
            agent, body.message, body.new, prompts_first_lines
        )
        # Create background tasks correctly
        background_tasks = BackgroundTasks()

        async def update_tokens_after_stream():
            logger.debug(f"Metrics before update: {agent.run_response.metrics}")
            # Ensure metrics are available after stream completes
            if agent.run_response and agent.run_response.metrics:
                await token_tracker.update_user_token_usage(
                    user_id=body.user_id,
                    metrics=agent.run_response.metrics,
                )
            else:
                logger.error("Metrics not available after streaming completed")
        
        background_tasks.add_task(update_tokens_after_stream)
        
        return StreamingResponse(
            response_generator,
            media_type="text/event-stream",
            background=background_tasks
        )
    else:
        response: RunResponse = agent.run(body.message, stream=False)
        response_content = response.content
        if is_sensitive_content(response_content, prompts_first_lines):
            response_content = "Sorry, I'm not able to respond to that request."

            # Add token tracking as a background task
        async def update_tokens_after_response():
            if response and response.metrics:
                await token_tracker.update_user_token_usage(
                    user_id=body.user_id,
                    metrics=response.metrics,
                )
            else:
                logger.error("Metrics not available for non-streaming response")

        background_tasks.add_task(update_tokens_after_response)

        # Prepare the response data
        response_data = (
            {"session_id": agent.session_id, "response": response_content}
            if body.new
            else {"response": response_content}
        )
        
        # Return JSONResponse with background tasks
        return JSONResponse(
            content=response_data,
            background=background_tasks
        )

@router.post("/chat-summary")
@auth_middleware.requires_auth
async def chat_summary(request: Request, body: ChatSummaryRequest):
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


# from fastapi import APIRouter
# from fastapi.responses import StreamingResponse, JSONResponse
# from app.models.schemas import ChatRequest, ChatSummaryRequest
# from phi.agent import Agent, RunResponse
# from app.core.assistants import (
#     get_assistant
# )
# from app.core.prompts.base import (
#     prompt,
#     instructions
# )
# from app.core.prompts.content import (
#     reel_script_prompt,
#     story_script_prompt,
#     general_instruction
# )
# from app.utils.helpers import chat_response_streamer, is_sensitive_content
# from app.core.assistants import storage
# import logging
# from typing import Optional, List
# from app.core.prompts.base import get_summary_prompt_with_context

# logger = logging.getLogger(__name__)
# router = APIRouter()

# @router.post("/chat")
# async def chat(body: ChatRequest):
#     """Sends a message to an Assistant and returns the response"""

#     # cancel_flag.clear()

#     logger.debug(f"ChatRequest: {body}")

#     # Determine session_id based on conditions
#     if body.new:
#         session_id = None  # New session will be created by the agent
#     elif body.session_id:
#         session_id = body.session_id  # Use provided session_id
#     else:
#         # Fetch the latest session_id if neither condition is met
#         existing_session_ids: List[str] = storage.get_all_session_ids(body.user_id)
#         print(f"existing_session_ids: {existing_session_ids}")
#         session_id = existing_session_ids[0] if existing_session_ids else None
    
#     agent = (get_assistant(
#         session_id=session_id,
#         user_id=body.user_id,
#         template_category=body.template_category,
#         is_speech_to_speech=body.is_speech_to_speech
#     ))

#     # session_id = agent.session_id
#     # print(f"Started Run: {session_id}")
    
#     # Comment out after first run
#     # agent.knowledge.load(recreate=False)

#     extra_prompt = general_instruction

#     # Conditionally set extra_prompt based on template_category
#     if body.template_category == "REELS_IDEAS":
#         extra_prompt = reel_script_prompt()[0]
#     elif body.template_category == "STORY_IDEAS":
#         extra_prompt = story_script_prompt()[0]

#     prompts_first_lines = [
#         prompt.split("\n")[0],
#         instructions[0],
#     ]

#     if extra_prompt:
#         prompts_first_lines.append(extra_prompt)

#     if body.stream:
#         return StreamingResponse(
#             chat_response_streamer(
#                 agent, body.message, body.new, prompts_first_lines
#             ),
#             media_type="text/event-stream",
#         )
#     else:
#         response: RunResponse = agent.run(body.message, stream=False)
#         response_content = response.content
#         if is_sensitive_content(response_content, prompts_first_lines):
#             response_content = "Sorry, I'm not able to respond to that request."
#         # Only include session_id in response if it's a new session
#         return JSONResponse(
#             {"session_id": agent.session_id, "response": response_content} if body.new
#             else {"response": response_content}
#         )

# @router.post("/chat-summary")
# async def chat_summary(body: ChatSummaryRequest):
#     """Generates a summary title for the most recent chat message"""
#     logger.debug(f"ChatSummaryRequest: {body}")

#     agent = (get_assistant(
#         session_id=body.session_id,
#         user_id=body.user_id
#     ))

#     summary_prompt_with_context = get_summary_prompt_with_context(body.recent_message)
#     response: RunResponse = agent.run(summary_prompt_with_context, stream=False)
#     summary = response.content

#     return JSONResponse({"response": summary})