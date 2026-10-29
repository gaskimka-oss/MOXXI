"""Расшифровка голосовых и кружков в текст.

Работает через:
  1) Google Gemini (Multimodal Native Audio & Video Notes) — мгновенно и без ограничений!
  2) Groq / OpenAI Whisper — если задан STT_API_KEY.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import urllib.request
import urllib.error
import uuid

log = logging.getLogger("irisbot.stt")

_STT_KEY = (os.getenv("STT_API_KEY") or "").strip()
_AI_KEY = (os.getenv("AI_API_KEY") or "").strip()

KEY = _STT_KEY or (_AI_KEY if _AI_KEY.startswith(("gsk_", "sk-proj-"))
                   or (_AI_KEY.startswith("sk-") and not _AI_KEY.startswith("sk-or-"))
                   else "")


def _guess_url() -> tuple[str, str]:
    if KEY.startswith("gsk_"):
        return ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3-turbo")
    return ("https://api.openai.com/v1/audio/transcriptions", "whisper-1")


_URL_GUESS, _MODEL_GUESS = _guess_url()
URL = (os.getenv("STT_API_URL") or _URL_GUESS).strip()
MODEL = (os.getenv("STT_MODEL") or _MODEL_GUESS).strip()

MAX_SECONDS = int(os.getenv("STT_MAX_SECONDS", "300") or 300)
MAX_BYTES = int(os.getenv("STT_MAX_BYTES", "25000000") or 25_000_000)
TIMEOUT = int(os.getenv("STT_TIMEOUT", "60") or 60)


def available() -> bool:
    try:
        import core_ai as ai
        return bool(KEY or ai.KEYS)
    except Exception:
        return bool(KEY)


def provider() -> str:
    if KEY:
        u = URL.lower()
        if "groq" in u:
            return "Groq Whisper"
        if "openai" in u:
            return "OpenAI Whisper"
        return "Whisper Server"
    try:
        import core_ai as ai
        if ai.KEYS:
            return "Google Gemini Multimodal AI"
    except Exception:
        pass
    return "не подключен"


def _post_audio(audio: bytes, filename: str = "voice.ogg") -> str | None:
    if not KEY:
        return None
    boundary = "----moxxi" + uuid.uuid4().hex
    nl = b"\r\n"
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.append(b"--" + boundary.encode() + nl)
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode() + nl + nl)
        parts.append(value.encode() + nl)

    field("model", MODEL)
    field("response_format", "json")
    field("temperature", "0")

    parts.append(b"--" + boundary.encode() + nl)
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode() + nl)
    parts.append(b"Content-Type: application/octet-stream" + nl + nl)
    parts.append(audio + nl)
    parts.append(b"--" + boundary.encode() + b"--" + nl)
    body = b"".join(parts)

    req = urllib.request.Request(
        URL, body,
        {"Authorization": f"Bearer {KEY}",
         "Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.load(r)
        text = (data.get("text") or "").strip()
        return text or None
    except Exception as e:
        log.warning("Whisper расшифровка не удалась: %s", str(e)[:200])
        return None


def _transcribe_gemini_sync(audio: bytes, mime_type: str = "audio/ogg") -> str | None:
    """Быстрая нативная расшифровка аудио/кружочка через Google Gemini с ротацией ключей."""
    try:
        import core_ai as ai
        if not ai.KEYS:
            return None

        prompt_instruction = (
            "Транскрибируй речь человека из этого видео-кружочка дословно на русском языке. "
            "Выведи ТОЛЬКО расшифрованный текст того, что он говорит. "
            "Никаких описаний видео, никаких комментариев, никаких вводных слов, никаких служебных мыслей."
            if mime_type.startswith("video/") else
            "Транскрибируй эту речь дословно на языке оригинала (русский). "
            "Выведи ТОЛЬКО расшифрованный текст сообщения. "
            "Никаких вводных слов, никаких комментариев, никаких кавычек, никаких служебных мыслей."
        )

        b64_data = base64.b64encode(audio).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_data
                            }
                        },
                        {
                            "text": prompt_instruction
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 1000
            }
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Пробуем доступные ключи с ротацией
        max_tries = min(len(ai.KEYS), 4)
        for _ in range(max_tries):
            current_key = ai.get_next_key()
            for m in ["gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-flash-latest"]:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={current_key}"
                req = urllib.request.Request(endpoint, data=body, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        cand = res_data.get("candidates") or []
                        if not cand:
                            continue
                        parts = cand[0].get("content", {}).get("parts") or []
                        clean_parts = [p for p in parts if not p.get("thought")] or parts
                        text = "".join(p.get("text", "") for p in clean_parts).strip()
                        text = re.sub(r"<thought>[\s\S]*?</thought>", "", text, flags=re.IGNORECASE).strip()
                        # Очищаем от обрамляющих кавычек
                        text = re.sub(r'^[«"\'`](.*)[»"\'`]$', r'\1', text).strip()
                        low = text.lower()
                        if low in {"тишина", "[тишина]", "(тишина)", "*тишина*", "звуков нет", "нет речи", "музыка", "[музыка]", "молчит"}:
                            return None
                        # Если нет ни одной буквы (только таймкоды, цифры или знаки) — речи нет
                        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", text):
                            return None
                        if text:
                            return text
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        break  # переходим к следующему ключу
                    continue
                except Exception as e:
                    log.warning("Gemini STT ошибка: %s", str(e)[:100])
                    continue
    except Exception as e:
        log.warning("Критическая ошибка Gemini STT: %s", e)

    return None


async def transcribe(audio: bytes, filename: str = "voice.ogg", mime_type: str = "audio/ogg") -> str | None:
    """Голосовое или кружок -> текст. Поддерживает Whisper и Google Gemini."""
    if not audio or len(audio) > MAX_BYTES:
        return None

    # 1. Если есть отдельный Whisper ключ (Groq/OpenAI)
    if KEY:
        try:
            res = await asyncio.to_thread(_post_audio, audio, filename)
            if res:
                return res
        except Exception:
            pass

    # 2. Если Whisper не сработал или ключ отсутствует — используем Gemini Multimodal AI
    try:
        return await asyncio.to_thread(_transcribe_gemini_sync, audio, mime_type)
    except Exception as e:
        log.warning("Ошибка транскрибации: %s", e)
        return None


def status() -> str:
    """Текст для команды «расшифровка»."""
    if not available():
        return (
            "🎙 <b>Расшифровка голосовых сообщений</b>\n\n"
            "Состояние: <b>🔴 не подключена</b>\n\n"
            "Бот может слушать голосовые и кружочки и мгновенно присылать их текст."
        )
    return (
        f"🎙 <b>Расшифровка голосовых и кружочков</b>\n\n"
        f"Состояние: <b>🟢 работает автоматически</b>\n"
        f"Сервис: <b>{provider()}</b>\n"
        f"Лимит длины: <b>{MAX_SECONDS // 60} мин</b>\n\n"
        f"✨ Бот слушает любые входящие голосовые сообщения и кружочки и сразу пишет текст в ответ без всяких команд!"
    )
