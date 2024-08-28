from typing import List, Generator
from phi.assistant import Assistant
from difflib import SequenceMatcher
# import threading

def chat_response_streamer(
    assistant: Assistant,
    message: str,
    is_new_session: bool,
    prompts_first_lines: List[str],
    # cancel_flag: threading.Event
) -> Generator:
    if is_new_session:
        yield f"run_id: {assistant.run_id}\n"

    accumulated_chunk = ""
    buffer = ""
    for chunk in assistant.run(message):
        # if cancel_flag.is_set():
        #     yield "[CANCELLED]\n\n"
        #     return
        accumulated_chunk += chunk
        buffer += chunk
        if is_sensitive_content(accumulated_chunk, prompts_first_lines):
            yield "Sorry, I'm not able to respond to that request."
            yield "[DONE]\n\n"
            return

        # Only yield complete sentences or phrases
        while "." in buffer or "," in buffer or "\n" in buffer:
            index = min(
                i
                for i in (buffer.find("."), buffer.find(","), buffer.find("\n"))
                if i != -1
            )
            yield buffer[: index + 1]
            buffer = buffer[index + 1 :]

    if buffer:  # Yield any remaining content
        yield buffer
    yield "[DONE]\n\n"

# this function check if any prompt is present in the response chunk
def is_sensitive_content(chunk: str, prompts_first_lines: List[str]) -> bool:
    chunk_lines = chunk.split("\n")
    return any(
        any(
            similar(chunk_line.lower(), first_line.lower())
            for first_line in prompts_first_lines
        )
        for chunk_line in chunk_lines
    )

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio() > 0.8

exports = chat_response_streamer, is_sensitive_content