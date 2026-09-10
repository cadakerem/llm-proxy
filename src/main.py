import os
import json
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
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

# Always load .env from the project root (parent of src/)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Debug: confirm keys loaded
logger.info(f"GROQ_KEY loaded: {bool(os.environ.get('GROQ_API_KEY'))}")
logger.info(f"NVIDIA_KEY loaded: {bool(os.environ.get('NVIDIA_API_KEY'))}")
logger.info(f"TARGET_MODELS: {os.environ.get('TARGET_MODELS')}")


app = FastAPI(title="Custom Claude CLI Proxy")

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.environ.get("GROQ_API_KEY")
    },
    "nvidia": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "key": os.environ.get("NVIDIA_API_KEY")
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key": os.environ.get("OPENAI_API_KEY")
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": os.environ.get("GEMINI_API_KEY")
    },
    "local": {
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "key": "dummy-key"
    }
}

TARGET_MODELS = [m.strip() for m in os.environ.get("TARGET_MODELS", "openai:gpt-4o").split(",") if m.strip()]

@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    return response

def anthropic_to_openai(anthropic_payload: Dict[str, Any], target_model: str) -> Dict[str, Any]:
    messages = []
    
    if "system" in anthropic_payload and anthropic_payload["system"]:
        messages.append({"role": "system", "content": anthropic_payload["system"]})
        
    for msg in anthropic_payload.get("messages", []):
        content = ""
        if isinstance(msg.get("content"), str):
            content = msg["content"]
        elif isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if block.get("type") == "text":
                    content += block.get("text", "")
                    
        messages.append({"role": msg.get("role", "user"), "content": content})

    return {
        "model": target_model,
        "messages": messages,
        "temperature": anthropic_payload.get("temperature", 0.7),
        "max_tokens": min(anthropic_payload.get("max_tokens", 4096), 16000)
    }

def openai_to_anthropic(openai_response: Dict[str, Any]) -> Dict[str, Any]:
    choices = openai_response.get("choices", [])
    if not choices:
        return {}
        
    choice = choices[0]
    message_content = choice.get("message", {}).get("content", "")
    
    return {
        "id": openai_response.get("id", "msg_mock"),
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet-20240620", 
        "content": [{"type": "text", "text": message_content}],
        "stop_reason": "end_turn" if choice.get("finish_reason") == "stop" else choice.get("finish_reason"),
        "stop_sequence": None,
        "usage": {
            "input_tokens": openai_response.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": openai_response.get("usage", {}).get("completion_tokens", 0)
        }
    }

@app.api_route("/api/hello", methods=["GET", "HEAD", "POST"])
async def health_check():
    return {"status": "ok"}

@app.post("/v1/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    # Return a fake token count so Claude CLI doesn't block
    return {"input_tokens": 100}

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
            logger.warning(f"Provider {provider_name} missing key. Skipping...")
            continue
            
        openai_payload = anthropic_to_openai(body, model_name.strip())
        headers = {
            "Authorization": f"Bearer {provider['key']}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Routing task to -> [{provider_name.upper()}] {model_name}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    provider["url"],
                    json=openai_payload,
                    headers=headers,
                    timeout=90.0
                )
                response.raise_for_status()
                target_data = response.json()
                
            logger.info(f"Success! Response received from {provider_name.upper()}")
            
            anthropic_resp = openai_to_anthropic(target_data)
            
            if body.get("stream", False):
                from fastapi.responses import StreamingResponse
                
                async def fake_stream():
                    yield f'event: message_start\ndata: {{"type": "message_start", "message": {{"id": "{anthropic_resp.get("id")}", "type": "message", "role": "assistant", "model": "{anthropic_resp.get("model")}", "content": [], "stop_reason": null, "stop_sequence": null, "usage": {json.dumps(anthropic_resp.get("usage", {}))}}}}}\n\n'
                    yield f'event: content_block_start\ndata: {{"type": "content_block_start", "index": 0, "content_block": {{"type": "text", "text": ""}}}}\n\n'
                    
                    text_content = anthropic_resp.get("content", [{}])[0].get("text", "")
                    
                    # Yield the text delta in a single fast chunk
                    yield f'event: content_block_delta\ndata: {{"type": "content_block_delta", "index": 0, "delta": {{"type": "text_delta", "text": {json.dumps(text_content)}}}}}\n\n'
                    
                    yield f'event: content_block_stop\ndata: {{"type": "content_block_stop", "index": 0}}\n\n'
                    
                    yield f'event: message_delta\ndata: {{"type": "message_delta", "delta": {{"stop_reason": "end_turn", "stop_sequence": null}}, "usage": {{"output_tokens": {anthropic_resp.get("usage", {}).get("output_tokens", 0)}}}}}\n\n'
                    yield f'event: message_stop\ndata: {{"type": "message_stop"}}\n\n'
                
                return StreamingResponse(fake_stream(), media_type="text/event-stream")
            else:
                return anthropic_resp
            
        except Exception as e:
            error_body = ""
            if hasattr(e, 'response') and e.response is not None:
                error_body = e.response.text[:500]
            logger.error(f"Failed via {provider_name.upper()} ({model_name}): {str(e)} | Response: {error_body}")
            continue
            
    logger.error("CRITICAL: All configured models exhausted.")
    raise HTTPException(status_code=500, detail="All configured proxy fallbacks exhausted.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
