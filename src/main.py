import os
import json
import logging
from typing import Dict, Any, List, AsyncGenerator
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from dotenv import load_dotenv
from pathlib import Path

log_file = Path(__file__).parent.parent / "proxy.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
logger = logging.getLogger("claude-proxy")

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Custom Claude CLI Proxy")

PROVIDERS = {
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "key": os.environ.get("GROQ_API_KEY")},
    "nvidia": {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "key": os.environ.get("NVIDIA_API_KEY")},
    "openai": {"url": "https://api.openai.com/v1/chat/completions", "key": os.environ.get("OPENAI_API_KEY")},
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "key": os.environ.get("GEMINI_API_KEY")},
    "local": {"url": "http://127.0.0.1:11434/v1/chat/completions", "key": "dummy-key"}
}

TARGET_MODELS = [m.strip() for m in os.environ.get("TARGET_MODELS", "openai:gpt-4o").split(",") if m.strip()]

def anthropic_to_openai_tools(anthropic_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not anthropic_tools:
        return []
    return [{
        "type": "function",
        "function": {
            "name": t.get("name"),
            "description": t.get("description", ""),
            "parameters": t.get("input_schema", {})
        }
    } for t in anthropic_tools]

def anthropic_to_openai_messages(anthropic_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    openai_msgs = []
    for msg in anthropic_messages:
        role = msg.get("role", "user")
        content = msg.get("content", [])
        
        if isinstance(content, str):
            openai_msgs.append({"role": role, "content": content})
            continue

        text_parts = []
        tool_calls = []
        
        for block in content:
            b_type = block.get("type")
            if b_type == "text":
                text_parts.append(block.get("text", ""))
            elif b_type == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })
            elif b_type == "tool_result":
                is_error = block.get("is_error", False)
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = "".join([c.get("text", "") for c in result_content if c.get("type") == "text"])
                elif not isinstance(result_content, str):
                    result_content = json.dumps(result_content)
                
                if is_error:
                    result_content = f"Error: {result_content}"
                
                # Each tool_result becomes a separate "tool" message in OpenAI
                openai_msgs.append({
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id"),
                    "content": result_content
                })
                
        # If there were text parts or tool calls, append them as the main message
        if text_parts or tool_calls:
            main_msg = {"role": "assistant" if role == "assistant" else "user"}
            if text_parts:
                main_msg["content"] = "".join(text_parts)
            if tool_calls:
                main_msg["tool_calls"] = tool_calls
            if not text_parts and tool_calls:
                main_msg["content"] = None # Some APIs expect null when only tool_calls are present
            openai_msgs.append(main_msg)
            
    return openai_msgs

def translate_payload(anthropic_payload: Dict[str, Any], target_model: str) -> Dict[str, Any]:
    payload = {
        "model": target_model,
        "messages": anthropic_to_openai_messages(anthropic_payload.get("messages", [])),
        "temperature": anthropic_payload.get("temperature", 0.7),
        "max_tokens": min(anthropic_payload.get("max_tokens", 4096), 16000),
        "stream": anthropic_payload.get("stream", False)
    }
    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}
    if "system" in anthropic_payload and anthropic_payload["system"]:
        sys_msg = anthropic_payload["system"]
        if isinstance(sys_msg, list):
            sys_msg = "".join([s.get("text", "") for s in sys_msg if s.get("type") == "text"])
        payload["messages"].insert(0, {"role": "system", "content": sys_msg})
        
    tools = anthropic_to_openai_tools(anthropic_payload.get("tools", []))
    if tools:
        payload["tools"] = tools
        
    return payload

import uuid

async def parse_openai_stream(response: httpx.Response) -> AsyncGenerator[str, None]:
    msg_id = f"msg_{uuid.uuid4().hex}"
    
    # 1. Start message
    yield f'event: message_start\ndata: {{"type": "message_start", "message": {{"id": "{msg_id}", "type": "message", "role": "assistant", "model": "claude-3-5-sonnet", "content": [], "stop_reason": null, "stop_sequence": null, "usage": {{"input_tokens": 0, "output_tokens": 0}}}}}}\n\n'
    
    open_blocks = set()
    stop_reason_val = "end_turn"
    final_usage = {"input_tokens": 0, "output_tokens": 0}
    
    async for line in response.aiter_lines():
        line = line.strip()
        if not line or line == "data: [DONE]":
            continue
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                
                # Check for usage info (if include_usage was set)
                if "usage" in data and data["usage"]:
                    final_usage["input_tokens"] = data["usage"].get("prompt_tokens", 0)
                    final_usage["output_tokens"] = data["usage"].get("completion_tokens", 0)
                
                choices = data.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                
                # Handling Text Content
                if "content" in delta and delta["content"]:
                    if 0 not in open_blocks:
                        yield f'event: content_block_start\ndata: {{"type": "content_block_start", "index": 0, "content_block": {{"type": "text", "text": ""}}}}\n\n'
                        open_blocks.add(0)
                    text = delta["content"]
                    yield f'event: content_block_delta\ndata: {{"type": "content_block_delta", "index": 0, "delta": {{"type": "text_delta", "text": {json.dumps(text)}}}}}\n\n'
                
                # Handling Tool Calls
                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0) + 1 # Offset by 1 in case text is block 0
                        
                        if tc.get("id"): # New tool call start
                            # Close text block if open to keep things ordered
                            if 0 in open_blocks:
                                yield f'event: content_block_stop\ndata: {{"type": "content_block_stop", "index": 0}}\n\n'
                                open_blocks.remove(0)
                                
                            fn_name = tc.get("function", {}).get("name", "")
                            
                            safe_id = json.dumps(tc.get("id"))
                            safe_name = json.dumps(fn_name)
                            
                            yield f'event: content_block_start\ndata: {{"type": "content_block_start", "index": {idx}, "content_block": {{"type": "tool_use", "id": {safe_id}, "name": {safe_name}, "input": {{}}}}}}\n\n'
                            open_blocks.add(idx)
                        
                        args = tc.get("function", {}).get("arguments", "")
                        if args:
                            yield f'event: content_block_delta\ndata: {{"type": "content_block_delta", "index": {idx}, "delta": {{"type": "input_json_delta", "partial_json": {json.dumps(args)}}}}}\n\n'
                
                # Handling Stop / Finish
                finish_reason = choices[0].get("finish_reason")
                if finish_reason:
                    # Close all remaining open blocks
                    for b_idx in list(open_blocks):
                        yield f'event: content_block_stop\ndata: {{"type": "content_block_stop", "index": {b_idx}}}\n\n'
                        open_blocks.remove(b_idx)
                    
                    if finish_reason == "tool_calls":
                        stop_reason_val = "tool_use"
                    
            except json.JSONDecodeError:
                pass
                
    yield f'event: message_delta\ndata: {{"type": "message_delta", "delta": {{"stop_reason": "{stop_reason_val}", "stop_sequence": null}}, "usage": {{"output_tokens": {final_usage["output_tokens"]}, "input_tokens": {final_usage["input_tokens"]}}}}}\n\n'
    yield f'event: message_stop\ndata: {{"type": "message_stop"}}\n\n'

def openai_to_anthropic_sync(openai_response: Dict[str, Any]) -> Dict[str, Any]:
    choices = openai_response.get("choices", [])
    if not choices:
        return {}
    choice = choices[0]
    msg = choice.get("message", {})
    
    content_blocks = []
    if msg.get("content"):
        content_blocks.append({"type": "text", "text": msg.get("content")})
        
    for tc in msg.get("tool_calls", []):
        try:
            args = json.loads(tc.get("function", {}).get("arguments", "{}"))
        except:
            args = {}
        content_blocks.append({
            "type": "tool_use",
            "id": tc.get("id"),
            "name": tc.get("function", {}).get("name"),
            "input": args
        })
        
    finish_reason = choice.get("finish_reason")
    stop_reason = "end_turn"
    if finish_reason == "tool_calls":
        stop_reason = "tool_use"
        
    return {
        "id": openai_response.get("id", f"msg_{uuid.uuid4().hex}"),
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet", 
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": openai_response.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": openai_response.get("usage", {}).get("completion_tokens", 0)
        }
    }

@app.middleware("http")
async def log_requests(request: Request, call_next):
    return await call_next(request)

@app.api_route("/api/hello", methods=["GET", "HEAD", "POST"])
async def health_check():
    return {"status": "ok"}

@app.post("/v1/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    # Lightweight heuristic: ~4 characters per token
    estimated_tokens = len(str(body)) // 4
    return {"input_tokens": max(estimated_tokens, 10)}

@app.post("/v1/messages")
async def create_message(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    if not TARGET_MODELS:
        raise HTTPException(status_code=500, detail="No target models configured in .env")
        
    for model_str in TARGET_MODELS:
        if ":" in model_str:
            provider_name, model_name = model_str.split(":", 1)
        else:
            provider_name, model_name = "openai", model_str
            
        provider = PROVIDERS.get(provider_name.strip().lower())
        if not provider or not provider.get("key"):
            continue
            
        openai_payload = translate_payload(body, model_name.strip())
        headers = {
            "Authorization": f"Bearer {provider['key']}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Routing task to -> [{provider_name.upper()}] {model_name}")
        
        try:
            client = httpx.AsyncClient()
            if openai_payload.get("stream"):
                # Handle SSE Stream
                req = client.build_request("POST", provider["url"], json=openai_payload, headers=headers, timeout=90.0)
                response = await client.send(req, stream=True)
                response.raise_for_status()
                
                async def stream_and_close():
                    try:
                        async for chunk in parse_openai_stream(response):
                            yield chunk
                    finally:
                        await response.aclose()
                        await client.aclose()
                        
                return StreamingResponse(stream_and_close(), media_type="text/event-stream")
            else:
                # Handle Sync
                response = await client.post(provider["url"], json=openai_payload, headers=headers, timeout=90.0)
                response.raise_for_status()
                await client.aclose()
                return openai_to_anthropic_sync(response.json())
            
        except Exception as e:
            error_body = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    await e.response.aread()
                    error_body = e.response.text[:500]
                except:
                    pass
            logger.error(f"Failed via {provider_name.upper()} ({model_name}): {str(e)} | {error_body}")
            continue
            
    logger.error("CRITICAL: All configured models exhausted.")
    raise HTTPException(status_code=500, detail="All configured proxy fallbacks exhausted.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
