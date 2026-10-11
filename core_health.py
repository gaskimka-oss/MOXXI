"""Мини-HTTP-сервер для healthcheck хостинга и раздачи Telegram Mini App (Web App).

Отвечает 200 OK и отдаёт HTML-интерфейс WebApp казино и хаба.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger("moxxibot.health")

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "webapp" / "index.html"


def _get_webapp_body() -> bytes:
    if HTML_PATH.exists():
        try:
            return HTML_PATH.read_bytes()
        except Exception:
            pass
    return b"<!DOCTYPE html><html><body><h1>Moxxi Bot is Healthy</h1></body></html>"


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        try:
            await asyncio.wait_for(reader.read(1024), timeout=3)
        except asyncio.TimeoutError:
            pass

        body = _get_webapp_body()
        resp = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n" + body
        )
        writer.write(resp)
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def start() -> asyncio.AbstractServer | None:
    raw = os.getenv("PORT") or os.getenv("HTTP_PORT") or "8080"
    try:
        port = int(str(raw).strip())
    except ValueError:
        port = 8080
    try:
        server = await asyncio.start_server(_handle, "0.0.0.0", port)
        log.info("HTTP WebApp & Healthcheck слушает порт %d", port)
        return server
    except Exception as e:
        log.warning("HTTP сервер не запущен (%s)", e)
        return None
