# -*- coding: utf-8 -*-
"""MOXXI Omnichannel Ticket Sync Bridge (Telegram ⇄ Discord ⇄ VK ⇄ MAX).

Обеспечивает сквозную синхронизацию тикетов поддержки:
1. Игрок пишет в поддержку в TG, DS, VK или MAX.
2. Карточка тикета мгновенно появляется И в Telegram Штабе, И в Discord очереди жалоб.
3. Если модератор берёт тикет в Discord ➔ в Telegram карточка моментально блокируется и пишется «Занят в Discord».
4. Если модератор берёт тикет в Telegram ➔ в Discord карточка моментально блокируется и пишется «Занят в Telegram».
5. Ответ улетает игроку прямо на его родную платформу.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

log = logging.getLogger("moxxi-ticket-bridge")


def get_tg_token() -> str:
    tok = os.getenv("BOT_TOKEN", "").strip() or os.getenv("TG_BOT_TOKEN", "").strip()
    if not tok:
        try:
            import config
            tok = getattr(config, "BOT_TOKEN", "")
        except Exception:
            pass
    return tok


def get_discord_token() -> str:
    tok = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not tok:
        # Ищем в соседней папке MOXXI Support
        cur = os.path.dirname(os.path.abspath(__file__))
        for p in [os.path.join(os.path.dirname(cur), "MOXXI Support", ".env"), os.path.join(os.path.dirname(cur), "moxxidc", ".env")]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith("DISCORD_BOT_TOKEN="):
                                tok = line.split("=", 1)[1].strip()
                                if tok:
                                    return tok
                except Exception:
                    pass
    return tok


def get_discord_guild_id() -> int:
    raw = os.getenv("STAFF_GUILD_ID") or os.getenv("DISCORD_GUILD_ID", "1568851684875046974")
    return int(raw) if str(raw).isdigit() else 1568851684875046974


async def init_bridge_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS omnichannel_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            text TEXT NOT NULL,
            category TEXT DEFAULT 'Общее',
            status TEXT DEFAULT 'open',
            claimed_by TEXT DEFAULT '',
            claimed_platform TEXT DEFAULT '',
            claimed_at REAL DEFAULT 0,
            tg_chat_id INTEGER DEFAULT 0,
            tg_msg_id INTEGER DEFAULT 0,
            tg_thread_id INTEGER DEFAULT 0,
            ds_channel_id INTEGER DEFAULT 0,
            ds_msg_id INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        )
    """)


# ---------------- 1. ОТПРАВКА И ОБНОВЛЕНИЕ ЧЕРЕЗ DISCORD REST API ----------------
def _discord_api_request(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> Optional[dict]:
    ds_token = get_discord_token()
    if not ds_token:
        return None
    url = f"https://discord.com/api/v10{endpoint}"
    headers = {
        "Authorization": f"Bot {ds_token}",
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot (https://moxxi, 1.0)"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except Exception as e:
        log.warning("Discord REST API Error (%s %s): %s", method, endpoint, e)
        return None


def get_discord_queue_channel_id() -> Optional[int]:
    """Ищет канал 🚨・очередь-жалоб на сервере стаффа Discord."""
    guild_id = get_discord_guild_id()
    res = _discord_api_request(f"/guilds/{guild_id}/channels")
    if not res or not isinstance(res, list):
        return None
    for ch in res:
        name = ch.get("name", "")
        if "очередь" in name or "жалоб" in name or "тикет" in name:
            return int(ch["id"])
    for ch in res:
        if ch.get("type") == 0:
            return int(ch["id"])
    return None


def send_ticket_to_discord(ticket_id: int, platform: str, user_name: str, user_id: str, text: str, category: str = "Общее") -> Optional[tuple[int, int]]:
    """Отправляет интерактивную карточку тикета в Discord."""
    ch_id = get_discord_queue_channel_id()
    if not ch_id:
        return None

    platform_icons = {"tg": "✈️ Telegram", "telegram": "✈️ Telegram", "vk": "🔷 ВКонтакте", "ds": "🎮 Discord", "discord": "🎮 Discord", "max": "⚡️ MAX"}
    p_label = platform_icons.get(platform.lower(), platform.upper())

    payload = {
        "embeds": [
            {
                "title": f"🎫 НОВОЕ ОБРАЩЕНИЕ • #{ticket_id} [{p_label}]",
                "description": (
                    f"👤 **Игрок:** `{user_name}` (ID: `{user_id}`)\n"
                    f"📱 **Платформа:** `{p_label}`\n"
                    f"📂 **Категория:** `{category}`\n"
                    f"⏱ **Время:** <t:{int(time.time())}:R>\n\n"
                    f"───────────────────────────────\n"
                    f"📝 **Вопрос / Проблема:**\n{text[:1500]}\n"
                    f"───────────────────────────────"
                ),
                "color": 16753920,
                "footer": {"text": "MOXXI Omnichannel Support Desk • Синхронизация TG ⇄ DS"}
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 3,
                        "label": "✋ Взять тикет",
                        "custom_id": f"st_omni_claim:{ticket_id}",
                        "emoji": {"name": "💬"}
                    }
                ]
            }
        ]
    }

    res = _discord_api_request(f"/channels/{ch_id}/messages", method="POST", data=payload)
    if res and res.get("id"):
        return ch_id, int(res["id"])
    return None


def update_discord_ticket_claimed(channel_id: int, message_id: int, ticket_id: int, mod_name: str, platform_from: str = "Telegram"):
    """Обновляет карточку в Discord, когда тикет взят в Telegram или Discord."""
    payload = {
        "embeds": [
            {
                "title": f"🟡 ТИКЕТ #{ticket_id} ВЗЯТ В РАБОТУ В {platform_from.upper()}!",
                "description": (
                    f"👮 **Модератор:** `{mod_name}` ({platform_from})\n"
                    f"⏳ **Статус:** `В обработке (занят)`\n\n"
                    f"───────────────────────────────\n"
                    f"💡 *Модератор изучает обращение.*\n"
                    f"Выберите действие ниже для ответа игроку."
                ),
                "color": 16763904,  # Gold
                "footer": {"text": "MOXXI Omnichannel Sync • В работе"}
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 1,
                        "label": "🤖 Авто-ответ ИИ",
                        "custom_id": f"st_omni_ai:{ticket_id}",
                        "emoji": {"name": "🤖"}
                    },
                    {
                        "type": 2,
                        "style": 2,
                        "label": "✍️ Ответить",
                        "custom_id": f"st_omni_reply:{ticket_id}",
                        "emoji": {"name": "✍️"}
                    }
                ]
            }
        ]
    }
    _discord_api_request(f"/channels/{channel_id}/messages/{message_id}", method="PATCH", data=payload)


def update_discord_ticket_answered(channel_id: int, message_id: int, ticket_id: int, mod_name: str, answer_text: str):
    """Обновляет карточку в Discord, когда ответ отправлен игроку. Появляется кнопка закрытия!"""
    ans_snippet = (answer_text[:300] + "...") if len(answer_text) > 300 else answer_text
    payload = {
        "embeds": [
            {
                "title": f"🟢 ТИКЕТ #{ticket_id} • ОТВЕТ ОТПРАВЛЕН ИГРОКУ",
                "description": (
                    f"👮 **Модератор:** `{mod_name}`\n"
                    f"✅ **Статус:** `Ответ успешно доставлен игроку`\n\n"
                    f"───────────────────────────────\n"
                    f"✉️ **Текст ответа:**\n«{ans_snippet}»\n"
                    f"───────────────────────────────\n"
                    f"🔒 *Когда вопрос полностью решён, нажмите кнопку ниже для закрытия тикета.*"
                ),
                "color": 65280,  # Green
                "footer": {"text": "MOXXI Omnichannel Sync • Ответ отправлен"}
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 4,
                        "label": "🔒 Закрыть тикет",
                        "custom_id": f"st_omni_close:{ticket_id}",
                        "emoji": {"name": "🔒"}
                    },
                    {
                        "type": 2,
                        "style": 2,
                        "label": "✍️ Дополнить ответ",
                        "custom_id": f"st_omni_reply:{ticket_id}",
                        "emoji": {"name": "✍️"}
                    }
                ]
            }
        ]
    }
    _discord_api_request(f"/channels/{channel_id}/messages/{message_id}", method="PATCH", data=payload)


def update_discord_ticket_closed(channel_id: int, message_id: int, ticket_id: int, mod_name: str):
    """Обновляет карточку в Discord, когда тикет окончательно закрыт."""
    payload = {
        "embeds": [
            {
                "title": f"🔒 ТИКЕТ #{ticket_id} • ЗАКРЫТ",
                "description": (
                    f"👮 **Закрыл:** `{mod_name}`\n"
                    f"🔒 **Статус:** `Закрыт администрацией`\n"
                    f"⏱ **Время:** <t:{int(time.time())}:R>\n\n"
                    f"───────────────────────────────\n"
                    f"Обращение полностью завершено и отправлено в архив."
                ),
                "color": 3092790,  # Dark Grey
                "footer": {"text": "MOXXI Omnichannel Sync • Закрыто"}
            }
        ],
        "components": []
    }
    _discord_api_request(f"/channels/{channel_id}/messages/{message_id}", method="PATCH", data=payload)


# ---------------- 2. ОТПРАВКА И ОБНОВЛЕНИЕ ЧЕРЕЗ TELEGRAM BOT API ----------------
def _telegram_api_request(method_name: str, payload: dict) -> Optional[dict]:
    tg_token = get_tg_token()
    if not tg_token:
        return None
    url = f"https://api.telegram.org/bot{tg_token}/{method_name}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except Exception as e:
        log.warning("Telegram Bot API Error (%s): %s", method_name, e)
        return None


def update_telegram_ticket_claimed(chat_id: int, message_id: int, ticket_id: int, mod_name: str, platform_from: str = "Discord"):
    """Обновляет карточку в Telegram, когда тикет взят в Discord."""
    text = (
        f"🔒 <b>[ТИКЕТ #{ticket_id} ВЗЯТ В РАБОТУ В {platform_from.upper()}]</b>\n\n"
        f"👮 <b>Модератор:</b> <code>{html.escape(mod_name)}</code> ({platform_from})\n"
        f"⏳ <b>Статус:</b> <code>В обработке (занят)</code>\n\n"
        f"───────────────────────────────\n"
        f"💡 <i>Коллега уже решает обращение в {platform_from}!</i>\n"
        f"В Telegram тикет автоматически заблокирован от повторного забора."
    )
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": f"🔒 Занят в {platform_from} ({mod_name})", "callback_data": f"omni_busy:{ticket_id}"}]
            ]
        }
    }
    _telegram_api_request("editMessageText", payload)
