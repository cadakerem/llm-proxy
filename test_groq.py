import httpx

import os
key = os.environ.get("GROQ_API_KEY", "your-api-key")
url = "https://api.groq.com/openai/v1/models"
headers = {"Authorization": f"Bearer {key}"}

try:
    with httpx.Client() as client:
        r = client.get(url, headers=headers)
        if r.status_code == 200:
            models = r.json().get("data", [])
            for m in models:
                print(m["id"])
        else:
            print("Status:", r.status_code, r.text)
except Exception as e:
    print("Error:", str(e))
