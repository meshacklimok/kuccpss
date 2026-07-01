"""Run this to verify OCR setup: conda run -n base python test_ocr_setup.py"""
from dotenv import load_dotenv
import os

load_dotenv('.env')
key = os.environ.get('OPENAI_API_KEY', '')

print("=== OCR Setup Check ===")

if not key or key.startswith('sk-your'):
    print("FAIL  API key not set — edit .env and add your real key")
else:
    print(f"OK    API key loaded: {key[:12]}...{key[-4:]}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        # Simple text-only test (no image, no cost)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': 'Reply with the single word: READY'}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip()
        if 'READY' in reply.upper():
            print("OK    OpenAI connection works — OCR is ready to use!")
        else:
            print(f"OK    Connected (got: {reply})")
    except Exception as e:
        print(f"FAIL  Connection error: {e}")
