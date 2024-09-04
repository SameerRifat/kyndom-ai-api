# OpneAI LLM:
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Generator, Dict, Any
from phi.assistant import Assistant, AssistantMemory, AssistantKnowledge, AssistantRun
from phi.storage.assistant.postgres import PgAssistantStorage
from phi.knowledge.pdf import PDFUrlKnowledgeBase
from phi.vectordb.pgvector import PgVector2
from phi.memory.db.postgres import PgMemoryDb
from phi.embedder.openai import OpenAIEmbedder
from textwrap import dedent
import logging
from fastapi.middleware.cors import CORSMiddleware
from phi.tools.duckduckgo import DuckDuckGo
from sqlalchemy import text
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json
from typing import List, Dict, Any
from utils import chat_response_streamer, is_sensitive_content

from intro_knowledge_base import intro_knowledge_base
# from kyndom_knowledge_base import kyndom_knowledge_base
# from combined_knowledge_base import knowledge_base
from phi.llm.aws.claude import Claude
from phi.llm.openai import OpenAIChat
# import threading

# import prompt
from system_prompt import prompt
from system_prompt import (
    instructions,
    extra_instructions_prompt,
    speech_to_speech_prompt,
    speech_to_speech_instructions,
    summary_prompt
)
from content_prompt import reel_script_prompt, story_script_prompt, general_instruction

from mongodb_search import mongodb_search

logger = logging.getLogger(__name__)


class CustomPgAssistantStorage(PgAssistantStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_all_run_info(self, user_id: str) -> List[Dict[str, Any]]:
        run_ids = self.get_all_run_ids(user_id)
        run_info_list = []

        query = text(
            f"""
        SELECT run_id, assistant_data, run_data, memory
        FROM {self.schema}.{self.table_name}
        WHERE run_id = ANY(:run_ids)
        ORDER BY created_at DESC
        """
        )

        with self.Session() as session:
            result = session.execute(query, {"run_ids": run_ids})
            rows = result.fetchall()

            for row in rows:
                run_id, assistant_data, run_data, memory = row

                # Handle cases where data might be string or dict
                if isinstance(assistant_data, str):
                    assistant_data = json.loads(assistant_data)
                elif assistant_data is None:
                    assistant_data = {}

                if isinstance(run_data, str):
                    run_data = json.loads(run_data)
                elif run_data is None:
                    run_data = {}

                if isinstance(memory, str):
                    memory = json.loads(memory)
                elif memory is None:
                    memory = {}

                chat_history = memory.get("chat_history", [])

                # Get the last response from chat_history where role is 'assistant'
                last_response = None
                for entry in reversed(chat_history):
                    if entry["role"] == "assistant":
                        last_response = entry["content"]
                        break

                run_info = {
                    "run_id": run_id,
                    "template_id": assistant_data.get("template_id")
                    or run_data.get("template_id"),
                    "template_title": assistant_data.get("template_title")
                    or run_data.get("template_title"),
                    "template_data": assistant_data,
                    "last_response": last_response,  # Add last_response to the run_info
                }
                run_info_list.append(run_info)

        return run_info_list


# Initialize the custom storage
db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
storage = CustomPgAssistantStorage(table_name="my_assistant", db_url=db_url)


app = FastAPI()
router = APIRouter()

# Configure CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://app.kyndom.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_assistant_params(
    run_id: Optional[str],
    user_id: Optional[str],
    template_category: Optional[str] = None,
    template_title: Optional[str] = None,
    template_id: Optional[str] = None,
    template_tag: Optional[str] = None,
    include_assistant_data: bool = True,
    is_speech_to_speech: bool = False,
) -> dict:
    assistant_params = {
        # "llm": Claude(
        #     model="claude-3-sonnet-20240229",
        #     api_key=
        # ),
        "llm": OpenAIChat(model="gpt-4o", max_tokens=4096, temperature=0.3),
        "description": prompt,
        # "instructions": instructions.copy(),  # Create a copy to modify
        "instructions": (
            speech_to_speech_instructions if is_speech_to_speech else instructions
        ),
        "run_id": run_id,
        "user_id": user_id,
        "storage": storage,
        # "tools": [mongodb_search],
        "tools": [DuckDuckGo(), mongodb_search],
        "search_knowledge": True,
        "read_chat_history": True,
        "create_memories": True,
        "show_tool_calls": True,
        "memory": AssistantMemory(
            db=PgMemoryDb(
                db_url=db_url,
                table_name="personalized_assistant_memory",
            )
        ),
        "update_memory_after_run": True,
        "knowledge_base": intro_knowledge_base,
        "add_references_to_prompt": True,
        "add_chat_history_to_messages": True,
        "introduction": dedent(
            """\
            Hi, I'm your personalized Assistant called Kynda AI.
            I can remember details about your preferences and solve problems.
            Let's get started!\
            """
        ),
        "prevent_hallucinations": True,
        "debug_mode": False,
    }

    # Add speech_to_speech_prompt to instructions if speech_to_speech is True
    # if is_speech_to_speech:
    #     assistant_params["instructions"].extend(speech_to_speech_prompt)
    if is_speech_to_speech:
        # assistant_params["read_chat_history"] = False
        assistant_params["add_references_to_prompt"] = False

    if include_assistant_data:
        assistant_params["assistant_data"] = {
            "template_title": template_title,
            "template_id": template_id,
            "template_category": template_category,
            "template_tag": template_tag,
        }

    # Always add speech_to_speech_prompt to extra_instructions if is_speech_to_speech is True
    extra_instructions = []
    if template_id:
        if template_category == "REELS_IDEAS":
            extra_instructions = reel_script_prompt()
        elif template_category == "STORY_IDEAS":
            extra_instructions = story_script_prompt()

    if is_speech_to_speech:
        extra_instructions = speech_to_speech_prompt + extra_instructions

    extra_instructions.extend(extra_instructions_prompt)
    assistant_params["extra_instructions"] = extra_instructions

    return assistant_params


def get_assistant(
    run_id: Optional[str],
    user_id: Optional[str],
    template_category: Optional[str] = None,
    template_title: Optional[str] = None,
    template_id: Optional[str] = None,
    template_tag: Optional[str] = None,
    is_speech_to_speech: bool = False,
) -> Assistant:
    assistant_params = create_assistant_params(
        run_id=run_id,
        user_id=user_id,
        template_category=template_category,
        template_title=template_title,
        template_id=template_id,
        template_tag=template_tag,
        include_assistant_data=True,
        is_speech_to_speech=is_speech_to_speech,
    )
    return Assistant(**assistant_params)


def get_assistant2(
    run_id: Optional[str],
    user_id: Optional[str],
    template_id: Optional[str] = None,
    is_speech_to_speech: bool = False,
) -> Assistant:
    assistant_params = create_assistant_params(
        run_id=run_id,
        user_id=user_id,
        template_id=template_id,
        include_assistant_data=False,
        is_speech_to_speech=is_speech_to_speech,
    )
    return Assistant(**assistant_params)


def get_assistant_for_chat_summary(
    run_id: Optional[str], user_id: Optional[str]
) -> Assistant:
    assistant_params = {
        # "llm": Claude(
        #     model="anthropic.claude-3-sonnet-20240229-v1:0",
        #     api_key=
        # ),
        "llm": OpenAIChat(model="gpt-4o-mini", max_tokens=2048, temperature=0.3),
        "description": prompt,
        "instructions": instructions,
        "run_id": run_id,
        "user_id": user_id,
        "storage": storage,
        "tools": [DuckDuckGo()],
        "search_knowledge": True,
        "read_chat_history": True,
        "create_memories": True,
        "show_tool_calls": True,
        "memory": AssistantMemory(
            db=PgMemoryDb(
                db_url=db_url,
                table_name="personalized_assistant_memory",
            )
        ),
        "update_memory_after_run": True,
        # "knowledge_base": knowledge_base,
        "add_references_to_prompt": True,
        "add_chat_history_to_messages": True,
        "prevent_hallucinations": True,
        "debug_mode": False,
    }
    return Assistant(**assistant_params)

# cancel_flag = threading.Event()

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    run_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"
    new: bool = False
    template_category: Optional[str] = None
    template_title: Optional[str] = None
    template_id: Optional[str] = None
    template_tag: Optional[str] = None
    is_speech_to_speech: bool = False


@router.post("/chat")
async def chat(body: ChatRequest):
    """Sends a message to an Assistant and returns the response"""

    # cancel_flag.clear()

    logger.debug(f"ChatRequest: {body}")
    run_id: Optional[str] = body.run_id if body.run_id else None
    is_new_session = False

    if body.new:
        is_new_session = True
    elif run_id is None:  # Only fetch existing run_ids if run_id is not provided
        existing_run_ids: List[str] = storage.get_all_run_ids(body.user_id)
        if len(existing_run_ids) > 0:
            run_id = existing_run_ids[0]

    assistant: Assistant = (
        get_assistant(
            run_id=run_id,
            user_id=body.user_id,
            template_category=body.template_category,
            template_title=body.template_title,
            template_id=body.template_id,
            template_tag=body.template_tag,
            is_speech_to_speech=body.is_speech_to_speech,
        )
        if is_new_session
        else get_assistant2(
            run_id=run_id,
            user_id=body.user_id,
            template_id=body.template_id,
            is_speech_to_speech=body.is_speech_to_speech,
        )
    )
    # assistant.knowledge_base.load(recreate=False)
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
                assistant, body.message, is_new_session, prompts_first_lines
            ),
            media_type="text/event-stream",
        )
    else:
        response = assistant.run(body.message, stream=False)
        if is_sensitive_content(response, prompts_first_lines):
            response = "Sorry, I'm not able to respond to that request."
        if is_new_session:
            return JSONResponse({"run_id": assistant.run_id, "response": response})
        else:
            return JSONResponse({"response": response})
        
# @router.post("/cancel_stream")
# async def cancel_stream():
#     cancel_flag.set()
#     return {"status": "Stream cancelled"}


class ChatSummaryRequest(BaseModel):
    stream: bool = False
    run_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"


@router.post("/chat-summary")
async def chat(body: ChatSummaryRequest):
    """Sends a message to an Assistant and returns the response"""

    logger.debug(f"ChatRequest: {body}")

    assistant: Assistant = get_assistant_for_chat_summary(
        run_id=body.run_id,
        user_id=body.user_id,
    )

    summary = assistant.run(f"{summary_prompt}", stream=False)

    return JSONResponse({"response": summary.strip('"')})


class ChatHistoryRequest(BaseModel):
    run_id: str
    user_id: Optional[str] = None


@router.post("/history", response_model=List[Dict[str, Any]])
async def get_chat_history(body: ChatHistoryRequest):
    """Return the chat history for an Assistant run"""

    logger.debug(f"ChatHistoryRequest: {body}")
    assistant: Assistant = get_assistant(
        run_id=body.run_id, user_id=body.user_id, template_category=None
    )
    # Load the assistant from the database
    assistant.read_from_storage()

    chat_history = assistant.memory.get_chat_history()
    return chat_history


@router.get("/")
async def health_check():
    return "The health check is successful!"


class GetAllAssistantRunsRequest(BaseModel):
    user_id: str


@app.post("/get-all", response_model=List[AssistantRun])
def get_assistants(body: GetAllAssistantRunsRequest):
    """Return all Assistant runs for a user"""
    return storage.get_all_runs(user_id=body.user_id)


class RunInfo(BaseModel):
    run_id: str
    template_id: Optional[str] = None
    template_title: Optional[str] = None
    last_response: Optional[str] = None


class GetAllAssistantRunIdsRequest(BaseModel):
    user_id: str


@app.post("/get-all-ids", response_model=List[RunInfo])
def get_run_ids(body: GetAllAssistantRunIdsRequest):
    """Return all run_ids with template info for a user"""
    try:
        run_info_list = storage.get_all_run_info(user_id=body.user_id)
        return [RunInfo(**run_info) for run_info in run_info_list]
    except Exception as e:
        logger.exception("An error occurred in get_run_ids")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
