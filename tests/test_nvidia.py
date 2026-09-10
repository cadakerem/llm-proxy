import httpx
import os

key = os.environ.get("NVIDIA_API_KEY", "your-api-key")
url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
payload = {"model": "meta/llama-3.1-70b-instruct", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}

try:
    with httpx.Client() as client:
        r = client.post(url, json=payload, headers=headers)
        print("Status:", r.status_code)
        print("Response:", r.text)
except Exception as e:
    print("Error:", str(e))
