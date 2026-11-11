"""Единая кроссплатформенная система мульти-рассылки MOXXI 3.0.
Позволяет из одной точки (админки Telegram) отправлять промокоды и анонсы обновлений
сразу во все 4 поддерживаемые платформы:
- ✈️ Telegram (группы и чаты)
- 🟦 ВКонтакте (беседы и диалоги)
- 🟣 Discord (серверы и текстовые каналы)
- 🟢 MAX (чаты мессенджера)
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import ssl
import time
from typing import Dict, List, Optional, Set

import aiohttp
import aiosqlite
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import db

log = logging.getLogger("cross_broadcast")

# Настройки токенов
def _get_vk_token() -> str:
    return os.getenv("VK_BOT_TOKEN", "").strip()

def _get_dc_token() -> str:
    return os.getenv("DISCORD_BOT_TOKEN", "").strip() or os.getenv("DISCORD_TOKEN", "").strip()

def _get_max_token() -> str:
    return os.getenv("MAX_BOT_TOKEN", "").strip()

# Базы данных других платформ на локальном диске
VK_DB_PATH = os.path.abspath(r"C:\Users\eiema\OneDrive\Desktop\moxxivk\data\moxxi_vk.db")
DC_DB_PATH = os.path.abspath(r"C:\Users\eiema\OneDrive\Desktop\moxxidc\data\moxxi_dc.db")
MAX_DB_PATH = os.path.abspath(r"C:\Users\eiema\OneDrive\Desktop\moxximax\data\moxxi_max.db")


# ══════════════════════════════════════════════════════════════════
# 1. СИНХРОНИЗАЦИЯ ПРОМОКОДА В БАЗЫ ДАННЫХ ВСЕХ 4 БОТОВ
# ══════════════════════════════════════════════════════════════════

async def sync_promo_to_all_dbs(code: str, reward: int, uses: int, created_by: int = 8036974481) -> None:
    """Записывает промокод в базы данных всех 4 платформ, чтобы игроки могли ввести его везде."""
    now = int(time.time())
    db_paths = [VK_DB_PATH, DC_DB_PATH, MAX_DB_PATH]
    for p in db_paths:
        if os.path.exists(p):
            try:
                async with aiosqlite.connect(p) as conn:
                    await conn.execute(
                        "INSERT INTO promocodes (code, chat_id, reward, uses_left, created_by, ts) "
                        "VALUES (?, 0, ?, ?, ?, ?) "
                        "ON CONFLICT(code) DO UPDATE SET uses_left=excluded.uses_left, reward=excluded.reward",
                        (code.upper(), reward, uses, created_by, now)
                    )
                    await conn.commit()
                log.info("Промокод %s успешно синхронизирован в базу %s", code, p)
            except Exception as e:
                log.warning("Не удалось синхронизировать промокод в %s: %s", p, e)


# ══════════════════════════════════════════════════════════════════
# 2. РАССЫЛКА В ВКОНТАКТЕ (VK API)
# ══════════════════════════════════════════════════════════════════

async def broadcast_vk(text: str) -> int:
    """Рассылает сообщение во все активные беседы и диалоги ВКонтакте."""
    vk_token = _get_vk_token()
    if not vk_token:
        log.warning("VK_BOT_TOKEN не задан, пропуск рассылки в VK")
        return 0

    target_peer_ids: Set[int] = set()

    # 1. Получаем список бесед из локальной базы данных VK
    if os.path.exists(VK_DB_PATH):
        try:
            async with aiosqlite.connect(VK_DB_PATH) as conn:
                async with conn.execute("SELECT DISTINCT chat_id FROM chat_activity WHERE chat_id > 0") as cur:
                    for row in await cur.fetchall():
                        target_peer_ids.add(row[0])
                async with conn.execute("SELECT DISTINCT peer_id FROM chat_settings WHERE peer_id > 0") as cur:
                    for row in await cur.fetchall():
                        target_peer_ids.add(row[0])
        except Exception as e:
            log.warning("Ошибка чтения базы VK для рассылки: %s", e)

    # 2. Запрашиваем актуальные диалоги через VK API messages.getConversations
    clean_vk_text = re.sub(r"</?(?:b|i|code|u|s|pre|a|span|div)[^>]*>", "", text)
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.vk.com/method/messages.getConversations"
            params = {"access_token": vk_token, "count": 200, "v": "5.131"}
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                if "response" in data and "items" in data["response"]:
                    for item in data["response"]["items"]:
                        peer = item.get("conversation", {}).get("peer", {})
                        pid = peer.get("id")
                        if pid:
                            target_peer_ids.add(pid)
    except Exception as e:
        log.warning("Ошибка запроса messages.getConversations VK: %s", e)

    if not target_peer_ids:
        log.info("Нет целевых бесед VK для рассылки")
        return 0

    sent_count = 0
    async with aiohttp.ClientSession() as session:
        for pid in target_peer_ids:
            try:
                rnd = random.randint(1, 2147483647)
                send_url = "https://api.vk.com/method/messages.send"
                payload = {
                    "access_token": vk_token,
                    "peer_id": str(pid),
                    "message": clean_vk_text,
                    "random_id": str(rnd),
                    "v": "5.131"
                }
                async with session.post(send_url, data=payload, timeout=10) as s_resp:
                    res = await s_resp.json()
                    if "response" in res:
                        sent_count += 1
                await asyncio.sleep(0.08)
            except Exception as e:
                log.debug("Ошибка отправки VK в %s: %s", pid, e)

    log.info("Рассылка VK завершена. Доставлено в %d бесед", sent_count)
    return sent_count


# ══════════════════════════════════════════════════════════════════
# 3. РАССЫЛКА В DISCORD (DISCORD REST API)
# ══════════════════════════════════════════════════════════════════

async def broadcast_discord(text: str) -> int:
    """Рассылает сообщение в текстовые каналы всех серверов Discord, где находится бот."""
    dc_token = _get_dc_token()
    if not dc_token:
        log.warning("DISCORD_BOT_TOKEN не задан, пропуск рассылки в Discord")
        return 0

    # Преобразуем HTML теги в Discord Markdown
    dc_text = text
    dc_text = re.sub(r"<b>(.*?)</b>", r"**\1**", dc_text, flags=re.DOTALL)
    dc_text = re.sub(r"<i>(.*?)</i>", r"*\1*", dc_text, flags=re.DOTALL)
    dc_text = re.sub(r"<code>(.*?)</code>", r"`\1`", dc_text, flags=re.DOTALL)
    dc_text = re.sub(r"<pre>(.*?)</pre>", r"```\n\1\n```", dc_text, flags=re.DOTALL)
    dc_text = re.sub(r"</?[^>]+>", "", dc_text)

    headers = {
        "Authorization": f"Bot {dc_token}",
        "Content-Type": "application/json"
    }

    guilds = []
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get("https://discord.com/api/v10/users/@me/guilds", timeout=10) as resp:
                if resp.status == 200:
                    guilds = await resp.json()
    except Exception as e:
        log.warning("Ошибка получения серверов Discord: %s", e)
        return 0

    sent_count = 0
    async with aiohttp.ClientSession(headers=headers) as session:
        for g in guilds:
            gid = g.get("id")
            if not gid:
                continue
            # Получаем каналы сервера
            try:
                async with session.get(f"https://discord.com/api/v10/guilds/{gid}/channels", timeout=10) as c_resp:
                    if c_resp.status != 200:
                        continue
                    channels = await c_resp.json()

                # Ищем лучший текстовый канал (общий, чат или первый с type=0)
                target_ch = None
                for ch in channels:
                    if ch.get("type") == 0:  # GUILD_TEXT
                        name = ch.get("name", "").lower()
                        if any(k in name for k in ("общ", "чат", "general", "main", "основн", "игры")):
                            target_ch = ch["id"]
                            break
                        if not target_ch:
                            target_ch = ch["id"]

                if target_ch:
                    payload = {"content": dc_text[:1990]}
                    async with session.post(f"https://discord.com/api/v10/channels/{target_ch}/messages", json=payload, timeout=10) as m_resp:
                        if m_resp.status in (200, 201):
                            sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                log.debug("Ошибка отправки Discord в гильдию %s: %s", gid, e)

    log.info("Рассылка Discord завершена. Доставлено на %d серверов", sent_count)
    return sent_count


# ══════════════════════════════════════════════════════════════════
# 4. РАССЫЛКА В MAX (MAX PLATFORM API)
# ══════════════════════════════════════════════════════════════════

async def broadcast_max(text: str) -> int:
    """Рассылает сообщение в чаты мессенджера MAX."""
    max_token = _get_max_token()
    if not max_token:
        log.warning("MAX_BOT_TOKEN не задан, пропуск рассылки в MAX")
        return 0

    target_chat_ids: Set[str] = set()

    # Считываем известные чаты из локальной базы MAX
    if os.path.exists(MAX_DB_PATH):
        try:
            async with aiosqlite.connect(MAX_DB_PATH) as conn:
                try:
                    async with conn.execute("SELECT chat_id FROM max_chats") as cur:
                        for row in await cur.fetchall():
                            target_chat_ids.add(str(row[0]))
                except Exception:
                    pass
                try:
                    async with conn.execute("SELECT DISTINCT chat_id FROM chat_activity WHERE chat_id > 0") as cur:
                        for row in await cur.fetchall():
                            target_chat_ids.add(str(row[0]))
                except Exception:
                    pass
        except Exception as e:
            log.warning("Ошибка чтения базы MAX: %s", e)

    clean_max_text = re.sub(r"</?(?:b|i|code|u|s|pre|a|span|div)[^>]*>", "", text)
    if not target_chat_ids:
        log.info("Нет известных чатов MAX для рассылки")
        return 0

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    headers = {
        "Authorization": max_token,
        "Content-Type": "application/json"
    }

    sent_count = 0
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        for cid in target_chat_ids:
            try:
                url = f"https://platform-api2.max.ru/messages?chat_id={cid}"
                payload = {"text": clean_max_text}
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status in (200, 201):
                        sent_count += 1
                await asyncio.sleep(0.08)
            except Exception as e:
                log.debug("Ошибка отправки MAX в чат %s: %s", cid, e)

    log.info("Рассылка MAX завершена. Доставлено в %d чатов", sent_count)
    return sent_count


# ══════════════════════════════════════════════════════════════════
# 5. ГЛАВНЫЕ ФУНКЦИИ МУЛЬТИ-РАССЫЛКИ (TELEGRAM + VK + DISCORD + MAX)
# ══════════════════════════════════════════════════════════════════

async def cross_broadcast_promo(bot: Bot, code: str, reward: int, uses: int) -> Dict[str, int]:
    """Рассылает промокод одновременно в Telegram, VK, Discord и MAX,
    а также автоматически синхронизирует его активацию во все базы данных.
    """
    code_up = code.upper().strip()
    # 1. Синхронизируем промокод во все локальные базы ботов
    await sync_promo_to_all_dbs(code_up, reward, uses)

    # 2. Текст для Telegram
    tg_text = (
        "🎁 ✨ <b>ОФИЦИАЛЬНЫЙ ПРОМОКОД ОТ СОЗДАТЕЛЕЙ!</b> ✨ 🎁\n"
        "✦ ══ • ⊰ 💎 🪙 💰 ⚡ ⊱ • ══ ✦\n\n"
        "Внимание всем участникам! Создатели выпустили специальный промокод на халявные монеты:\n\n"
        f"🔑 Код: <code>{code_up}</code>\n"
        f"💰 Награда: <b>+{reward:,} монет</b> каждому!\n"
        f"👥 Всего активаций: <b>{uses} шт.</b> (успей забрать!)\n\n"
        "👉 <b>Как получить монеты:</b>\n"
        f"Нажмите кнопку ниже или напишите в чат: <code>промо {code_up}</code>\n\n"
        "✦ ══ • ⊰ 🍸 MOXXI 3.0 MULTIPLATFORM ⊱ • ══ ✦"
    )

    # 3. Текст для VK и MAX
    plain_text = (
        "🎁 ✨ ОФИЦИАЛЬНЫЙ ПРОМОКОД ОТ СОЗДАТЕЛЕЙ! ✨ 🎁\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Внимание всем игрокам проекта MOXXI 3.0!\n"
        "Создатели выпустили специальный промокод на халявные монеты:\n\n"
        f"🔑 Код: {code_up}\n"
        f"💰 Награда: +{reward:,} монет каждому!\n"
        f"👥 Всего активаций: {uses} шт. (успейте забрать!)\n\n"
        f"👉 Для получения монет напишите в чат: «промо {code_up}»!\n\n"
        "🚀 MOXXI 3.0 работает в Telegram, VK, Discord и MAX!"
    )

    # 4. Текст для Discord (с Markdown)
    dc_text = (
        "## 🎁 ✨ ОФИЦИАЛЬНЫЙ ПРОМОКОД ОТ СОЗДАТЕЛЕЙ! ✨ 🎁\n"
        "> Внимание всем участникам! Выпущен специальный промокод на халявные монеты MOXXI 3.0:\n\n"
        f"* 🔑 **Код:** `{code_up}`\n"
        f"* 💰 **Награда:** **+{reward:,} монет** каждому игроку!\n"
        f"* 👥 **Всего активаций:** **{uses} шт.**\n\n"
        f"👉 **Как получить:** Напишите в чат команду `!промо {code_up}` или `промо {code_up}`!\n"
        "🎮 *Играйте в MOXXI во всех любимых соцсетях!*"
    )

    results: Dict[str, int] = {
        "telegram": 0,
        "vk": 0,
        "discord": 0,
        "max": 0
    }

    # Запуск рассылки в Telegram
    from h_botinfo import broadcast_notice
    try:
        results["telegram"] = await broadcast_notice(bot, tg_text)
    except Exception as e:
        log.warning("Ошибка рассылки Telegram: %s", e)

    # Запуск параллельной рассылки на остальные платформы
    try:
        results["vk"] = await broadcast_vk(plain_text)
    except Exception as e:
        log.warning("Ошибка мульти-рассылки в VK: %s", e)

    try:
        results["discord"] = await broadcast_discord(dc_text)
    except Exception as e:
        log.warning("Ошибка мульти-рассылки в Discord: %s", e)

    try:
        results["max"] = await broadcast_max(plain_text)
    except Exception as e:
        log.warning("Ошибка мульти-рассылки в MAX: %s", e)

    return results


async def cross_broadcast_update(bot: Bot, update_texts: List[str]) -> Dict[str, int]:
    """Рассылает масштабный анонс обновления сразу на все платформы."""
    results: Dict[str, int] = {
        "telegram": 0,
        "vk": 0,
        "discord": 0,
        "max": 0
    }

    # 1. Telegram
    from h_botinfo import broadcast_notice
    for t in update_texts:
        try:
            c = await broadcast_notice(bot, t)
            results["telegram"] = max(results["telegram"], c)
        except Exception as e:
            log.warning("Ошибка рассылки апдейта в TG: %s", e)

    combined_text = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(update_texts)

    # 2. VK
    try:
        results["vk"] = await broadcast_vk(combined_text)
    except Exception as e:
        log.warning("Ошибка рассылки апдейта в VK: %s", e)

    # 3. Discord
    try:
        for t in update_texts:
            c = await broadcast_discord(t)
            results["discord"] = max(results["discord"], c)
    except Exception as e:
        log.warning("Ошибка рассылки апдейта в Discord: %s", e)

    # 4. MAX
    try:
        results["max"] = await broadcast_max(combined_text)
    except Exception as e:
        log.warning("Ошибка рассылки апдейта в MAX: %s", e)

    return results
