from fastapi import FastAPI, APIRouter
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

logger = logging.getLogger(__name__)

db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
storage = PgAssistantStorage(table_name="my_assistant", db_url=db_url)

app = FastAPI()
router = APIRouter()

origins = [
    "http://localhost:3000",  
    "http://127.0.0.1:3000",  
    "https://app.kyndom.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_dynamic_instructions(template_type):
    if template_type == "REELS_IDEAS":
        specific_instructions = [
            "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
            "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
            "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
            "4. Personalize the Reel Idea: Use the collected data my saved profile information to personalize the reel idea according to the user's preferences and the template's requirements.",
            "5. Tone: Ensure the tone of the personalized template is selected by the user.",
            "6. Format: Maintain the original format of the template.",
            "7. Length: Ensure the personalized template does not exceed 350 words.",
        ]
    elif template_type == "STORY_IDEAS":
        specific_instructions = [
            "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
            "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
            "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
            "4. Personalize the Story Idea: Use the collected data my saved profile information to personalize the story idea according to the user's preferences and the template's requirements.",
            "5. Tone: Ensure the tone of the personalized story idea is selected by the user.",
            "6. Format: Maintain the original format of the story idea.",
            "7. Length: Ensure the personalized story idea does not exceed 350 words."
        ]
    elif template_type == "TODAYS_PLAN":
        specific_instructions = [
            "This is a 'Today's Plan' template.",
            "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
            "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
            "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
            "4. Personalize the Idea: Use the collected data and my saved profile information to personalize the idea according to the user's preferences and the template's requirements.",
            "5. Tone: Ensure the tone of the personalized idea is selected by the user.",
            "6. Format: Maintain the original format of the idea.",
            "7. Length: Ensure the personalized idea does not exceed 350 words."
        ]
    else:
        specific_instructions = []

    return specific_instructions

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    run_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"
    new: bool = False
    template_type: Optional[str] = None

def get_assistant(run_id: Optional[str], user_id: Optional[str], template_type: Optional[str]) -> Assistant:
    assistant_params = {
        "description": "You are a real estate assistant for my real estate agency",
        "run_id": run_id,
        "user_id": user_id,
        "storage": storage,
        "tools": [DuckDuckGo()],
        "show_tool_calls": True,
        "search_knowledge": True,
        "read_chat_history": True,
        # "debug_mode": True,
        "create_memories": True,
        "memory": AssistantMemory(
            db=PgMemoryDb(
                db_url=db_url,
                table_name="personalized_assistant_memory",
            )
        ),
        "update_memory_after_run": True,
        "knowledge_base": AssistantKnowledge(
            vector_db=PgVector2(
                db_url=db_url,
                collection="personalized_assistant_documents",
                embedder=OpenAIEmbedder(model="text-embedding-3-small", dimensions=1536),
            ),
            num_documents=3,
        ),
        "add_chat_history_to_messages": True,
        "introduction": dedent(
            """\
            Hi, I'm your personalized Assistant called OptimusV7.
            I can remember details about your preferences and solve problems using tools and other AI Assistants.
            Let's get started!\
            """
        )
    }

    if template_type:
        assistant_params["instructions"] = get_dynamic_instructions(template_type)

    assistant = Assistant(**assistant_params)
    return assistant

def chat_response_streamer(assistant: Assistant, message: str, is_new_session: bool) -> Generator:
    if is_new_session:
        yield f"run_id: {assistant.run_id}\n"  
    for chunk in assistant.run(message):
        yield chunk
    yield "[DONE]\n\n"

@router.post("/chat")
async def chat(body: ChatRequest):
    """Sends a message to an Assistant and returns the response"""
    
    logger.debug(f"ChatRequest: {body}")
    run_id: Optional[str] = None
    is_new_session = False
    
    if body.new:
        is_new_session = True  
    else:
        existing_run_ids: List[str] = storage.get_all_run_ids(body.user_id)
        if len(existing_run_ids) > 0:
            run_id = existing_run_ids[0]
    
    assistant: Assistant = get_assistant(
        run_id=run_id, user_id=body.user_id, template_type=body.template_type
    )
    
    if body.stream:
        return StreamingResponse(
            chat_response_streamer(assistant, body.message, is_new_session),
            media_type="text/event-stream",
        )
    else:
        response = assistant.run(body.message, stream=False)
        if is_new_session:
            return JSONResponse({"run_id": assistant.run_id, "response": response})
        else:
            return JSONResponse({"response": response})
    
class ChatHistoryRequest(BaseModel):
    run_id: str
    user_id: Optional[str] = None


@router.post("/history", response_model=List[Dict[str, Any]])
async def get_chat_history(body: ChatHistoryRequest):
    """Return the chat history for an Assistant run"""

    logger.debug(f"ChatHistoryRequest: {body}")
    assistant: Assistant = get_assistant(
        run_id=body.run_id, user_id=body.user_id, template_type=None
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


class GetAllAssistantRunIdsRequest(BaseModel):
    user_id: str

@app.post("/get-all-ids", response_model=List[str])
def get_run_ids(body: GetAllAssistantRunIdsRequest):
    """Return all run_ids for a user"""
    return storage.get_all_run_ids(user_id=body.user_id)


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)





# from fastapi import FastAPI, APIRouter
# from fastapi.responses import StreamingResponse
# from pydantic import BaseModel
# from typing import Optional, List, Generator, Dict, Any
# from phi.assistant import Assistant, AssistantMemory, AssistantKnowledge
# from phi.storage.assistant.postgres import PgAssistantStorage
# from phi.knowledge.pdf import PDFUrlKnowledgeBase
# from phi.vectordb.pgvector import PgVector2
# from phi.memory.db.postgres import PgMemoryDb
# from phi.embedder.openai import OpenAIEmbedder
# from textwrap import dedent
# import logging
# from fastapi.middleware.cors import CORSMiddleware
# from phi.tools.duckduckgo import DuckDuckGo

# logger = logging.getLogger(__name__)

# db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
# storage = PgAssistantStorage(table_name="my_assistant", db_url=db_url)

# app = FastAPI()
# router = APIRouter()

# # Configure CORS
# origins = [
#     "http://localhost:3000",  
#     "http://127.0.0.1:3000",  
#     "https://app.kyndom.com"
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# def get_dynamic_instructions(template_type):
#     if template_type == "REELS_IDEAS":
#         specific_instructions = [
#             "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
#             "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
#             "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
#             "4. Personalize the Reel Idea: Use the collected data my saved profile information to personalize the reel idea according to the user's preferences and the template's requirements.",
#             "5. Tone: Ensure the tone of the personalized template is selected by the user.",
#             "6. Format: Maintain the original format of the template.",
#             "7. Length: Ensure the personalized template does not exceed 350 words.",
#         ]
#     # "2. Do Not Use Previous Reel Idea Information: Do not use the information from previous Reel Ideas for the current Reel Idea. Each Reel Idea should be treated independently.",
#     elif template_type == "STORY_IDEAS":
#         specific_instructions = [
#             "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
#             "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
#             "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
#             "4. Personalize the Story Idea: Use the collected data my saved profile information to personalize the story idea according to the user's preferences and the template's requirements.",
#             "5. Tone: Ensure the tone of the personalized story idea is selected by the user.",
#             "6. Format: Maintain the original format of the story idea.",
#             "7. Length: Ensure the personalized story idea does not exceed 350 words."
#         ]
#     # "2. Do Not Use Previous Information: Do not use the information from previous templates for the current template. Each template should be treated independently.",
#     elif template_type == "TODAYS_PLAN":
#         specific_instructions = [
#             "This is a 'Today's Plan' template.",
#             "1. Understand the Template's Purpose and Elements: Familiarize yourself with the purpose of the template and the key elements it contains.",
#             "2. Collect Data: Identify the user's preferences and any custom variables in the template. Based on the user's preferences, determine if additional information is needed to complete the custom variables. Ask the user one question at a time to gather the necessary data. Wait for the user's response before asking the next question. Limit the total number of questions to a maximum of 5.",
#             "3. If Needed, Search from the Web: Utilize external sources like DuckDuckGo to gather additional information if required.",
#             "4. Personalize the Idea: Use the collected data and my saved profile information to personalize the idea according to the user's preferences and the template's requirements.",
#             "5. Tone: Ensure the tone of the personalized idea is selected by the user.",
#             "6. Format: Maintain the original format of the idea.",
#             "7. Length: Ensure the personalized idea does not exceed 350 words."
#         ]
#     # "2. Do Not Use Previous Information: Do not use the information from previous templates for the current template. Each template should be treated independently.",
#     else:
#         specific_instructions = []

#     return specific_instructions

# class ChatRequest(BaseModel):
#     message: str
#     stream: bool = False
#     run_id: Optional[str] = None
#     user_id: Optional[str] = "user"
#     assistant: str = "RAG_PDF"
#     new: bool = False
#     template_type: Optional[str] = None

# def get_assistant(run_id: Optional[str], user_id: Optional[str], template_type: Optional[str]) -> Assistant:
#     assistant_params = {
#         "description": "You are a real estate assistant for my real estate agency",
#         "run_id": run_id,
#         "user_id": user_id,
#         "storage": storage,
#         "tools": [DuckDuckGo()],
#         "show_tool_calls": True,
#         "search_knowledge": True,
#         "read_chat_history": True,
#         # "debug_mode": True,
#         "create_memories": True,
#         "memory": AssistantMemory(
#             db=PgMemoryDb(
#                 db_url=db_url,
#                 table_name="personalized_assistant_memory",
#             )
#         ),
#         "update_memory_after_run": True,
#         "knowledge_base": AssistantKnowledge(
#             vector_db=PgVector2(
#                 db_url=db_url,
#                 collection="personalized_assistant_documents",
#                 embedder=OpenAIEmbedder(model="text-embedding-3-small", dimensions=1536),
#             ),
#             num_documents=3,
#         ),
#         "add_chat_history_to_messages": True,
#         "introduction": dedent(
#             """\
#             Hi, I'm your personalized Assistant called OptimusV7.
#             I can remember details about your preferences and solve problems using tools and other AI Assistants.
#             Let's get started!\
#             """
#         )
#     }

#     if template_type:
#         assistant_params["instructions"] = get_dynamic_instructions(template_type)

#     assistant = Assistant(**assistant_params)
#     return assistant

# def chat_response_streamer(assistant: Assistant, message: str) -> Generator:
#     for chunk in assistant.run(message):
#         yield chunk

# @router.post("/chat")
# async def chat(body: ChatRequest):
#     """Sends a message to an Assistant and returns the response"""

#     logger.debug(f"ChatRequest: {body}")
#     run_id: Optional[str] = None

#     if not body.new:
#         existing_run_ids: List[str] = storage.get_all_run_ids(body.user_id)
#         if len(existing_run_ids) > 0:
#             run_id = existing_run_ids[0]

#     assistant: Assistant = get_assistant(
#         run_id=run_id, user_id=body.user_id, template_type=body.template_type
#     )

#     if body.stream:
#         return StreamingResponse(
#             chat_response_streamer(assistant, body.message),
#             media_type="text/event-stream",
#         )
#     else:
#         response = assistant.run(body.message, stream=False)
#         return {"response": response}
    
# class ChatHistoryRequest(BaseModel):
#     run_id: str
#     user_id: Optional[str] = None


# @router.post("/history", response_model=List[Dict[str, Any]])
# async def get_chat_history(body: ChatHistoryRequest):
#     """Return the chat history for an Assistant run"""

#     logger.debug(f"ChatHistoryRequest: {body}")
#     assistant: Assistant = get_assistant(
#         run_id=body.run_id, user_id=body.user_id
#     )
#     # Load the assistant from the database
#     assistant.read_from_storage()

#     chat_history = assistant.memory.get_chat_history()
#     return chat_history

# @router.get("/")
# async def health_check():
#     return "The health check is successful!"

# app.include_router(router)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)