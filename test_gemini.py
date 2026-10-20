import urllib.request
import urllib.error
import json
import os
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[6] / "OneDrive" / "Desktop" / "бот2.0" / ".env")
raw_key = os.getenv('AI_API_KEY') or ''
key = raw_key.split(',')[0].strip()


test_models = [
    'gemini-2.5-flash',
    'gemini-flash-latest',
    'gemini-2.5-flash-lite',
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite-preview'
]

for m in test_models:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}'
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': 'Ответь Привет по-русски коротко'}]}]
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
            c = res.get('candidates', [{}])[0]
            parts = c.get('content', {}).get('parts', [])
            print(f'SUCCESS [{m}]: parts count={len(parts)}')
            for i, p in enumerate(parts):
                is_thought = p.get('thought', False)
                txt = repr(p.get('text', ''))[:100]
                print(f'   part {i} (thought={is_thought}): {txt}')
            break
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')[:150]
        print(f'FAIL [{m}]: HTTP {e.code} - {err_msg}')
    except Exception as e:
        print(f'FAIL [{m}]: {e}')
