from fastapi import FastAPI, APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Generator, Dict, Any
from phi.assistant import Assistant, AssistantMemory, AssistantKnowledge
from phi.storage.assistant.postgres import PgAssistantStorage
from phi.knowledge.pdf import PDFUrlKnowledgeBase
from phi.vectordb.pgvector import PgVector2
from phi.memory.db.postgres import PgMemoryDb
from phi.embedder.openai import OpenAIEmbedder
from textwrap import dedent
import logging
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
storage = PgAssistantStorage(table_name="my_assistant", db_url=db_url)

app = FastAPI()
router = APIRouter()

# Configure CORS
origins = [
    "http://localhost:3000",  # Your Next.js frontend
    "http://127.0.0.1:3000",  # Your Next.js frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    run_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"
    new: bool = False

def get_assistant(run_id: Optional[str], user_id: Optional[str]) -> Assistant:
    assistant = Assistant(
        run_id=run_id,
        user_id=user_id,
        storage=storage,
        show_tool_calls=True,
        search_knowledge=True,
        read_chat_history=True,
        # debug_mode=True,
        create_memories=True,
        memory=AssistantMemory(
            db=PgMemoryDb(
                db_url=db_url,
                table_name="personalized_assistant_memory",
            )
        ),
        update_memory_after_run=True,
        knowledge_base=AssistantKnowledge(
            vector_db=PgVector2(
                db_url=db_url,
                collection="personalized_assistant_documents",
                embedder=OpenAIEmbedder(model="text-embedding-3-small", dimensions=1536),
            ),
            num_documents=3,
        ),
        add_chat_history_to_messages=True,
        introduction=dedent(
            """\
            Hi, I'm your personalized Assistant called `OptimusV7`.
            I can remember details about your preferences and solve problems using tools and other AI Assistants.
            Let's get started!\
            """
        )
    )
    return assistant

def chat_response_streamer(assistant: Assistant, message: str) -> Generator:
    for chunk in assistant.run(message):
        yield chunk

@router.post("/chat")
async def chat(body: ChatRequest):
    """Sends a message to an Assistant and returns the response"""

    logger.debug(f"ChatRequest: {body}")
    run_id: Optional[str] = None

    if not body.new:
        existing_run_ids: List[str] = storage.get_all_run_ids(body.user_id)
        if len(existing_run_ids) > 0:
            run_id = existing_run_ids[0]

    assistant: Assistant = get_assistant(
        run_id=run_id, user_id=body.user_id
    )

    if body.stream:
        return StreamingResponse(
            chat_response_streamer(assistant, body.message),
            media_type="text/event-stream",
        )
    else:
        response = assistant.run(body.message, stream=False)
        return {"response": response}
    
class ChatHistoryRequest(BaseModel):
    run_id: str
    user_id: Optional[str] = None


@router.post("/history", response_model=List[Dict[str, Any]])
async def get_chat_history(body: ChatHistoryRequest):
    """Return the chat history for an Assistant run"""

    logger.debug(f"ChatHistoryRequest: {body}")
    assistant: Assistant = get_assistant(
        run_id=body.run_id, user_id=body.user_id
    )
    # Load the assistant from the database
    assistant.read_from_storage()

    chat_history = assistant.memory.get_chat_history()
    return chat_history

@router.get("/")
async def health_check():
    return "The health check is successful!"

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)