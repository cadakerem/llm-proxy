import httpx

key = "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"
url = "https://integrate.api.nvidia.com/v1/models"
headers = {"Authorization": f"Bearer {key}"}

try:
    with httpx.Client() as client:
        r = client.get(url, headers=headers)
        if r.status_code == 200:
            models = r.json().get("data", [])
            for m in models:
                if "llama" in m["id"].lower():
                    print(m["id"])
        else:
            print("Status:", r.status_code, r.text)
except Exception as e:
    print("Error:", str(e))
