import httpx
import asyncio
import json

async def test_e2e_tool_result():
    payload = {
        "model": "claude-3-5-sonnet",
        "system": "You have a tool to read files.",
        "messages": [
            {"role": "user", "content": "Go ahead and read README.md"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "fc_8ab5750f-fb9b-4f7c-8c6c-8020060950c8", "name": "read_file", "input": {"path": "README.md"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "fc_8ab5750f-fb9b-4f7c-8c6c-8020060950c8", "content": "The first feature is Full SSE Streaming!"}]}
        ],
        "max_tokens": 1000,
        "stream": True,
        "tools": [{
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }]
    }

    print("--- SENDING TOOL RESULT TO PROXY ---")
    async with httpx.AsyncClient() as client:
        req = client.build_request("POST", "http://127.0.0.1:8082/v1/messages", json=payload, headers={"ANTHROPIC_API_KEY": "dummy", "ANTHROPIC_VERSION": "2023-06-01"})
        resp = await client.send(req, stream=True)
        async for line in resp.aiter_lines():
            if line:
                print(line)

asyncio.run(test_e2e_tool_result())
