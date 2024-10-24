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

def is_sensitive_content(chunk: str, prompts_first_lines: List[str]) -> bool:
    chunk_lines = chunk.split("\n")
    return any(
        any(
            similar(chunk_line.lower(), first_line.lower())
            for first_line in prompts_first_lines
        )
        for chunk_line in chunk_lines
    )

def similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() > 0.8

exports = chat_response_streamer, is_sensitive_content

# from typing import List, Generator
# from phi.assistant import Assistant
# from difflib import SequenceMatcher

# def chat_response_streamer(
#     assistant: Assistant,
#     message: str,
#     is_new_session: bool,
#     prompts_first_lines: List[str],
# ) -> Generator:
#     if is_new_session:
#         yield f"run_id: {assistant.run_id}\n"

#     accumulated_chunk = ""
#     buffer = ""
#     for chunk in assistant.run(message):
#         accumulated_chunk += chunk
#         buffer += chunk
#         if is_sensitive_content(accumulated_chunk, prompts_first_lines):
#             yield "Sorry, I'm not able to respond to that request."
#             yield "[DONE]\n\n"
#             return

#         # Only yield complete sentences or phrases
#         while "." in buffer or "," in buffer or "\n" in buffer:
#             index = min(
#                 i
#                 for i in (buffer.find("."), buffer.find(","), buffer.find("\n"))
#                 if i != -1
#             )
#             yield buffer[: index + 1]
#             buffer = buffer[index + 1 :]

#     if buffer:  # Yield any remaining content
#         yield buffer
#     yield "[DONE]\n\n"

# # this function check if any prompt is present in the response chunk
# def is_sensitive_content(chunk: str, prompts_first_lines: List[str]) -> bool:
#     chunk_lines = chunk.split("\n")
#     return any(
#         any(
#             similar(chunk_line.lower(), first_line.lower())
#             for first_line in prompts_first_lines
#         )
#         for chunk_line in chunk_lines
#     )

# def similar(a, b):
#     return SequenceMatcher(None, a, b).ratio() > 0.8

# exports = chat_response_streamer, is_sensitive_content