from typing import Optional
from textwrap import dedent
from phi.assistant import AssistantMemory
from phi.agent import Agent, AgentMemory
from phi.model.openai import OpenAIChat
from phi.tools.duckduckgo import DuckDuckGo
from phi.memory.db.postgres import PgMemoryDb
from app.config import settings
from phi.storage.agent.postgres import PgAgentStorage

from app.core.prompts import (
    prompt,
    instructions,
    extra_instructions_prompt,
    speech_to_speech_prompt,
    speech_to_speech_instructions,
    get_summary_prompt_with_context,
)
# from app.core.knowledge_base import intro_knowledge_base
from app.core.prompts.content import (
    reel_script_prompt,
    story_script_prompt,
    general_instruction
)

from phi.knowledge.text import TextKnowledgeBase
from phi.vectordb.pgvector import PgVector

intro_knowledge_base = TextKnowledgeBase(
    path="data/intro.txt",
    # Table name: ai.text_documents
    vector_db=PgVector(
        table_name="text_documents",
        db_url=settings.DB_URL,
    ),
)

from app.core.tools import mongodb_search

storage = PgAgentStorage(table_name="my_assistant", db_url=settings.DB_URL)

def create_assistant_params(
    session_id: Optional[str],
    user_id: Optional[str],
    template_category: Optional[str] = None,
    is_speech_to_speech: bool = False,
) -> dict:
    agent_params = {
        "model": OpenAIChat(id="gpt-4o", max_tokens=4096, temperature=0.3),
        "description": prompt,
        "instructions": (
            speech_to_speech_instructions if is_speech_to_speech else instructions
        ),
        "session_id": session_id,
        "user_id": user_id,
        "memory": AgentMemory(
            db=PgMemoryDb(table_name="personalized_assistant_memory", db_url=settings.DB_URL),
            create_user_memories=True,
            create_session_summary=True
        ),
        "storage": storage,
        "tools": [DuckDuckGo(), mongodb_search],
        "search_knowledge": True,
        "read_chat_history": True,
        "create_memories": True,
        "show_tool_calls": True,
        "update_memory_after_run": True,
        "knowledge": intro_knowledge_base,
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

    if is_speech_to_speech:
        agent_params["add_references_to_prompt"] = False

    # Always add speech_to_speech_prompt to extra_instructions if is_speech_to_speech is True
    extra_instructions = []
    if template_category:
        if template_category == "REELS_IDEAS":
            extra_instructions = reel_script_prompt()
        elif template_category == "STORY_IDEAS":
            extra_instructions = story_script_prompt()

    if is_speech_to_speech:
        extra_instructions = speech_to_speech_prompt + extra_instructions

    extra_instructions.extend(extra_instructions_prompt)
    agent_params["extra_instructions"] = extra_instructions

    return agent_params


def get_assistant(
    session_id: Optional[str],
    user_id: Optional[str],
    template_category: Optional[str] = None,
    is_speech_to_speech: bool = False,
) -> Agent:
    agent_params = create_assistant_params(
        session_id=session_id,
        user_id=user_id,
        template_category=template_category,
        is_speech_to_speech=is_speech_to_speech,
    )
    return Agent(**agent_params)
