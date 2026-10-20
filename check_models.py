import urllib.request
import json
import time
import config
import core_ai as ai

key = ai.KEYS[0]
models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
]

payload = {
    "contents": [{"role": "user", "parts": [{"text": "Привет! Ответь одним словом."}]}],
    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20, "thinkingConfig": {"thinkingBudget": 0}}
}
body = json.dumps(payload).encode("utf-8")
headers = {"Content-Type": "application/json"}

for m in models_to_test:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
    req = urllib.request.Request(endpoint, data=body, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            dt = round(time.time() - t0, 2)
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
            text = parts[0].get("text", "").strip() if parts else ""
            print(f"MODEL {m}: OK in {dt}s -> '{text}'", flush=True)
    except urllib.error.HTTPError as e:
        dt = round(time.time() - t0, 2)
        print(f"MODEL {m}: HTTP {e.code} in {dt}s", flush=True)
    except Exception as e:
        dt = round(time.time() - t0, 2)
        print(f"MODEL {m}: ERROR {e} in {dt}s", flush=True)
