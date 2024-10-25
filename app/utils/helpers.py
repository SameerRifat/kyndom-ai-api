from typing import Generator, List, Iterator
from phi.agent import Agent, RunResponse
from difflib import SequenceMatcher

def chat_response_streamer(
    agent: Agent,
    message: str,
    is_new_session: bool,
    prompts_first_lines: List[str],
) -> Generator:
    if is_new_session:
        yield f"session_id: {agent.session_id}\n"
    accumulated_chunk = ""
    buffer = ""
    
    # Get streaming response
    response_stream: Iterator[RunResponse] = agent.run(message, stream=True)
    
    for response in response_stream:
        # Get the content from RunResponse
        chunk = response.content
        if not chunk:
            continue
            
        accumulated_chunk += chunk
        buffer += chunk
        
        if is_sensitive_content(accumulated_chunk, prompts_first_lines):
            yield "Sorry, I'm not able to respond to that request."
            yield "[DONE]\n\n"
            return

        # Only yield complete sentences or phrases
        while "." in buffer or "," in buffer or "\n" in buffer:
            delimiters = [pos for pos in (
                buffer.find("."), 
                buffer.find(","), 
                buffer.find("\n")
            ) if pos != -1]
            
            if not delimiters:
                break
                
            index = min(delimiters)
            yield buffer[: index + 1]
            buffer = buffer[index + 1 :]

    if buffer:  # Yield any remaining content
        yield buffer
    yield "[DONE]\n\n"

def is_sensitive_content(content: str, prompts_first_lines: List[str]) -> bool:
    """
    Check if the content contains sensitive information by comparing with prompt first lines.
    
    Args:
        content (str): The text content to check
        prompts_first_lines (List[str]): List of first lines from prompts to compare against
        
    Returns:
        bool: True if sensitive content is detected, False otherwise
    """
    content_lines = content.split("\n")
    return any(
        any(
            similar(content_line.lower(), first_line.lower())
            for first_line in prompts_first_lines
        )
        for content_line in content_lines
    )

def similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() > 0.8

def similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() > 0.8

exports = chat_response_streamer, is_sensitive_content