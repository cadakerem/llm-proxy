import httpx

import os
key = os.environ.get("GROQ_API_KEY", "your-api-key")
url = "https://api.groq.com/openai/v1/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
payload = {"model": "qwen/qwen3.8-27b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}
r = httpx.post(url, json=payload, headers=headers)
print(r.status_code, r.text)
