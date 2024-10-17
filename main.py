# OpneAI LLM:
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union
from phi.assistant import Assistant, AssistantMemory
from phi.storage.assistant.postgres import PgAssistantStorage
from phi.memory.db.postgres import PgMemoryDb
from textwrap import dedent
import logging
from fastapi.middleware.cors import CORSMiddleware
from phi.tools.duckduckgo import DuckDuckGo
from typing import List, Dict
from utils import chat_response_streamer, is_sensitive_content
import csv
from datetime import datetime

from intro_knowledge_base import intro_knowledge_base
from phi.llm.openai import OpenAIChat

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

# Initialize the custom storage
db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
# storage = CustomPgAssistantStorage(table_name="my_assistant", db_url=db_url)
storage = PgAssistantStorage(table_name="my_assistant", db_url=db_url)


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

class ChatSummaryRequest(BaseModel):
    stream: bool = False
    run_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"
    recent_message: str = Field(..., description="The most recent user message")

@router.post("/chat-summary")
async def chat(body: ChatSummaryRequest):
    """Generates a summary title for the most recent chat message"""

    logger.debug(f"ChatSummaryRequest: {body}")

    assistant: Assistant = get_assistant_for_chat_summary(
        run_id=body.run_id,
        user_id=body.user_id,
    )

    summary_prompt_with_context = f"""
    Previous message: {body.recent_message}

    1. Generate a concise 4-6 word summary title that clearly captures the main topic or objective of the previous chat message.
    2. Ensure that the summary is specific to the actual content discussed in the previous message.
    3. Avoid generic phrases or topics, such as 'general chat purpose,' 'assistant capabilities,' or 'lead generation strategies.'
    4. Exclude any tool names, irrelevant details, or broad generalizations.
    5. Focus solely on the key subject matter of the conversation.
    6. If the previous message is very brief or lacks specific content, make sure the summary is still relevant to the overall chat context.
    7. For specific messages, create a summary that accurately represents the main point of the conversation.
    8. For non-specific messages, aim to generate a summary that still captures the essence of the message while avoiding overly broad or generic terms.

    Based on the above context and guidelines, generate a summary title:
    """

    summary = assistant.run(summary_prompt_with_context, stream=False)

    return JSONResponse({"response": summary.strip('"')})


# class ChatSummaryRequest(BaseModel):
#     stream: bool = False
#     run_id: Optional[str] = None
#     user_id: Optional[str] = "user"
#     assistant: str = "RAG_PDF"


# @router.post("/chat-summary")
# async def chat(body: ChatSummaryRequest):
#     """Sends a message to an Assistant and returns the response"""

#     logger.debug(f"ChatRequest: {body}")

#     assistant: Assistant = get_assistant_for_chat_summary(
#         run_id=body.run_id,
#         user_id=body.user_id,
#     )

#     summary = assistant.run(f"{summary_prompt}", stream=False)

#     return JSONResponse({"response": summary.strip('"')})


@router.get("/")
async def health_check():
    return "The health check is successful!"
    
CSV_PATH = "./data/City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"

class ZHVIResponse(BaseModel):
    dates: List[str]
    regionData: List[Dict[str, Union[str, int, float, None]]]

# Initialize ZHVI data
headers = None
formatted_dates = None

def load_and_parse_csv():
    global headers, formatted_dates
    try:
        with open(CSV_PATH, 'r') as file:
            csv_reader = csv.reader(file)
            headers = next(csv_reader)
            
            if not headers:
                raise ValueError("CSV file is empty or contains only whitespace")
            
            date_columns = headers[8:]
            formatted_dates = []
            for date in date_columns:
                try:
                    # First try parsing as 'DD/MM/YYYY'
                    parsed_date = datetime.strptime(date, '%d/%m/%Y')
                except ValueError:
                    try:
                        # If it fails, try parsing as 'YYYY-MM-DD'
                        parsed_date = datetime.strptime(date, '%Y-%m-%d')
                    except ValueError as e:
                        logger.error(f"Error parsing date {date}: {e}")
                        formatted_dates.append(date)
                        continue  # Skip to the next date if parsing fails

                # If parsing is successful, format the date as 'YYYY-MM-DD'
                formatted_date = parsed_date.strftime('%Y-%m-%d')
                formatted_dates.append(formatted_date)
            
            return True
    except Exception as e:
        logger.error(f"Error loading CSV file: {e}")
        return False

# Load CSV data on startup
if not load_and_parse_csv():
    logger.error("Failed to load ZHVI data on startup")

@app.get("/api/zhvi/{region_name}/{state_name}", response_model=ZHVIResponse)
async def get_zhvi_data(region_name: str, state_name: str):
    if not headers or not formatted_dates:
        raise HTTPException(status_code=500, detail="ZHVI data not properly initialized")
    
    try:
        matching_record = None
        
        with open(CSV_PATH, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip headers
            
            for row in csv_reader:
                if len(row) < 8:
                    continue
                
                if (row[2].lower() == region_name.lower() and 
                    row[4].lower() == state_name.lower()):
                    record = {
                        "RegionID": int(row[0]) if row[0].isdigit() else 0,
                        "SizeRank": int(row[1]) if row[1].isdigit() else 0,
                        "RegionName": row[2],
                        "RegionType": row[3],
                        "StateName": row[4],
                        "State": row[5],
                        "Metro": row[6],
                        "CountyName": row[7]
                    }
                    
                    for i, date in enumerate(formatted_dates):
                        try:
                            value = float(row[i + 8]) if row[i + 8] else None
                            record[date] = value
                        except (IndexError, ValueError):
                            record[date] = None
                    
                    matching_record = record
                    break
        
        if not matching_record:
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for {region_name}, {state_name}"
            )
        
        return JSONResponse({
            "dates": formatted_dates,
            "regionData": [matching_record]
        })
    
    except Exception as e:
        logger.exception("An error occurred in get_zhvi_data")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)