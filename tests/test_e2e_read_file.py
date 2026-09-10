import httpx
import asyncio
import json
import sys

async def test_e2e():
    payload = {
        "model": "claude-3-5-sonnet",
        "system": "You have a tool to read files. Please read README.md and tell me what the first feature is.",
        "messages": [{"role": "user", "content": "Go ahead and read README.md"}],
        "max_tokens": 1000,
        "stream": True,
        "tools": [{
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }]
    }

    print("--- SENDING E2E REQUEST TO PROXY ---")
    with open('e2e_output.txt', 'w', encoding='utf-8') as f:
        async with httpx.AsyncClient() as client:
            req = client.build_request("POST", "http://127.0.0.1:8082/v1/messages", json=payload, headers={"ANTHROPIC_API_KEY": "dummy", "ANTHROPIC_VERSION": "2023-06-01"})
            resp = await client.send(req, stream=True)
            async for line in resp.aiter_lines():
                if line:
                    print(line)
                    f.write(line + '\n')
    print("--- DONE ---")

asyncio.run(test_e2e())
