from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union

class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    session_id: Optional[str] = None
    user_id: Optional[str] = "user"
    new: bool = False
    template_category: Optional[str] = None
    is_speech_to_speech: bool = False

class ChatSummaryRequest(BaseModel):
    stream: bool = False
    session_id: Optional[str] = None
    user_id: Optional[str] = "user"
    assistant: str = "RAG_PDF"
    recent_message: str = Field(..., description="The most recent user message")

class ZHVIResponse(BaseModel):
    dates: List[str]
    regionData: List[Dict[str, Union[str, int, float, None]]]
