# core.py
import json
import base64
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

# Initialize the OpenAI-compatible client for DashScope
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or "sk-1980181c4a2540a9bb234a989b641bc1"
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = os.getenv("FIONA_AGENT_MODEL") or "qvq-plus"

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)

def save_snapshot_image(snapshot_b64: str) -> str:
    """
    Decode base64 snapshot data and save it as a temporary PNG file.
    Returns a file path accessible to the chat API.
    """
    if not snapshot_b64:
        return None
    try:
        # Strip off data URL prefix if present
        if snapshot_b64.startswith("data:image"):
            header, data = snapshot_b64.split(",", 1)
        else:
            data = snapshot_b64
        binary = base64.b64decode(data)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp_file.write(binary)
        tmp_file.close()
        return tmp_file.name
    except Exception as e:
        print(f"[core.py] Snapshot decode failed: {e}")
        return None


def ollama_chat(
    messages: List[Dict[str, Any]],
    snapshot_b64: str = None,
    *,
    enable_thinking: bool = True,
    thinking_budget: int = 8192,
    model: str = DEFAULT_MODEL,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_handler: Optional[Callable[[str, Dict[str, Any], Optional[str]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Send a conversation to the vision model with optional snapshot context.
    Returns dict with reasoning + answer text.
    """
    image_url_block = None
    local_image_path = None
    normalized_snapshot_url = None

    # If a snapshot is provided, decode and save temporarily
    if snapshot_b64:
        local_image_path = save_snapshot_image(snapshot_b64)
        if snapshot_b64:
            normalized_snapshot_url = snapshot_b64.strip()
            if not normalized_snapshot_url.startswith("data:image"):
                normalized_snapshot_url = f"data:image/png;base64,{normalized_snapshot_url}"
            image_url_block = {
                "type": "image_url",
                "image_url": {"url": normalized_snapshot_url}
            }


    # Build messages for the chat API
    formatted_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = []
        if image_url_block and role == "user":
            content.append(image_url_block)
        if isinstance(msg.get("content"), list):
            content.extend(msg["content"])
        else:
            content.append({"type": "text", "text": str(msg.get("content", ""))})
        formatted_messages.append({"role": role, "content": content})

    executed_tool_calls: List[Dict[str, Any]] = []
    reasoning_accumulator: List[str] = []
    answer = ""

    if tools:
        conversation = formatted_messages[:]
        while True:
            completion = client.chat.completions.create(
                model=model,
                messages=conversation,
                tools=tools,
                stream=False,
                extra_body={
                    "enable_thinking": enable_thinking,
                    "thinking_budget": thinking_budget,
                },
            )
            if not completion.choices:
                break
            choice = completion.choices[0]
            message = getattr(choice, "message", None)
            if not message:
                break
            reasoning_text = getattr(message, "reasoning", None) or getattr(choice, "reasoning", None)
            if isinstance(reasoning_text, str):
                reasoning_accumulator.append(reasoning_text)
            elif isinstance(reasoning_text, list):
                reasoning_accumulator.extend(str(chunk) for chunk in reasoning_text)

            if message.tool_calls:
                conversation.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in message.tool_calls
                        ],
                    }
                )
                for tool_call in message.tool_calls:
                    args_payload: Dict[str, Any]
                    try:
                        args_payload = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args_payload = {"__raw": tool_call.function.arguments or "", "error": "invalid json"}
                    result_payload: Dict[str, Any]
                    if tool_handler:
                        try:
                            result_payload = tool_handler(tool_call.function.name, args_payload, tool_call.id)
                        except Exception as exc:  # pylint: disable=broad-except
                            result_payload = {"status": "error", "error": str(exc)}
                    else:
                        result_payload = {"status": "error", "error": "no tool handler configured"}
                    executed_tool_calls.append(
                        {
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "arguments": args_payload,
                            "result": result_payload,
                        }
                    )
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": json.dumps(result_payload, ensure_ascii=False),
                        }
                    )
                continue

            answer = message.content or ""
            conversation.append({"role": "assistant", "content": answer})
            break

    else:
        completion = client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            stream=True,
            extra_body={
                "enable_thinking": enable_thinking,
                "thinking_budget": thinking_budget
            }
        )

        print("\n" + "=" * 15 + " MODEL STREAM " + "=" * 15 + "\n")
        is_answering = False
        for chunk in completion:
            if not chunk.choices:
                if hasattr(chunk, "usage"):
                    print("\nUsage stats:", chunk.usage)
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "reasoning_content", None):
                print(delta.reasoning_content, end="", flush=True)
                reasoning_accumulator.append(delta.reasoning_content)
            else:
                if not is_answering and delta.content != "":
                    print("\n" + "=" * 20 + " Reply " + "=" * 20 + "\n")
                    is_answering = True
                print(delta.content, end="", flush=True)
                answer += delta.content

        print("\n" + "=" * 48 + "\n")

    answer_text = answer.strip()
    reasoning_text = "\n".join(chunk.strip() for chunk in reasoning_accumulator if chunk.strip())
    message_payload = {
        "role": "assistant",
        "content": [],
    }

    if answer_text:
        message_payload["content"].append({"type": "text", "text": answer_text})
    else:
        message_payload["content"].append({"type": "text", "text": "No response received."})

    if reasoning_text:
        message_payload["metadata"] = {"reasoning": reasoning_text}

    return {
        "message": message_payload,
        "answer": answer_text,
        "reasoning": reasoning_text,
        "tool_calls": executed_tool_calls,
    }


def remote_chat(messages: List[Dict[str, Any]], snapshot_b64: str = None, **kwargs):
    """
    Alias to ollama_chat for remote operation compatibility.
    (You can customize for a remote host if needed.)
    """
    return ollama_chat(messages, snapshot_b64, **kwargs)
