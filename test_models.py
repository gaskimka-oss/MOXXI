import sys
sys.path.insert(0, r"c:\Users\eiema\OneDrive\Desktop\бот2.0")

import urllib.request, urllib.error, json

keys = [
    'AQ.Ab8RN6KfKEd6hv_2WcPWRLK-lbYp-92dgTK8QhgiJ1Y3N6ymPA',
    'AQ.Ab8RN6LsAcLElV1Y-cMPKi4S5cKh6zavbcpP2J7Up-CymlMvBA'
]

models = [
    'gemini-3.1-flash-lite-preview',
    'gemini-3-flash-preview',
    'gemini-2.5-flash-lite',
    'gemini-flash-latest'
]

data = {
    'contents': [{'parts': [{'text': 'Ответь кратко: тест пройден'}]}],
    'generationConfig': {
        'responseMimeType': 'application/json',
        'maxOutputTokens': 1000
    }
}

for m in models:
    for k_idx, key in enumerate(keys, 1):
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}'
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                txt = res['candidates'][0]['content']['parts'][0]['text']
                print(f'[OK] Model: {m} | Key: #{k_idx} -> {txt.strip()[:60]}')
        except urllib.error.HTTPError as e:
            print(f'[FAIL] Model: {m} | Key: #{k_idx} -> HTTP {e.code}')
        except Exception as e:
            print(f'[ERR] Model: {m} | Key: #{k_idx} -> {e}')
