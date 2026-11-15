"""Бортовой журнал и система телеметрии MOXXI (MOXXI Health & Telemetry).

Фиксирует в течение дня:
1. Каждую выполненную команду с её полным текстом, временем выполнения (мс), пользователем и чатом.
2. Все случаи, когда бот не ответил или заблокировал действие (не та тема, нет анкеты, нехватка ранга, спам).
3. Все ошибки, краши и сбои Telegram API / базы данных с полным трейсом и контекстом.
4. Автоматическая очистка старых логов (хранение 7 дней).
5. Генерация отчётов за день для совместного разбора разработчиками.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time
import traceback
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from aiogram.types import ErrorEvent, Message

import config
import db

log = logging.getLogger("moxxibot.telemetry")

# Очередь для фоновой неблокирующей записи в БД
_log_queue: deque[dict[str, Any]] = deque()
_worker_task: Optional[asyncio.Task] = None
_MAX_QUEUE_SIZE = 5000
_CLEANUP_INTERVAL_SEC = 3600  # раз в час чистим записи старше 7 дней
_RETENTION_DAYS = 7


def _clean_text(text: Optional[str], max_len: int = 1000) -> str:
    """Очищает и обрезает текст сообщения для лога."""
    if not text:
        return ""
    # Маскируем токены ботов, если кто-то случайно прислал токен
    sanitized = re.sub(r"\d{8,11}:[A-Za-z0-9_-]{30,40}", "[REDACTED_BOT_TOKEN]", text)
    if len(sanitized) > max_len:
        return sanitized[:max_len] + "… [обрез]"
    return sanitized


def _get_dt_str(ts: int | None = None) -> str:
    """Возвращает дату/время в формате YYYY-MM-DD HH:MM:SS (МСК, UTC+3)."""
    t = ts if ts is not None else int(time.time())
    # Московское время (UTC+3)
    msk = timezone(timedelta(hours=3))
    return datetime.fromtimestamp(t, tz=msk).strftime("%Y-%m-%d %H:%M:%S")


async def init_telemetry() -> None:
    """Создаёт таблицы и индексы для бортового журнала."""
    try:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            dt TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            chat_id INTEGER,
            chat_title TEXT,
            thread_id INTEGER,
            user_id INTEGER,
            username TEXT,
            user_name TEXT,
            command_key TEXT,
            full_text TEXT,
            reason TEXT,
            stack_trace TEXT,
            execution_ms INTEGER DEFAULT 0
        )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_diag_ts ON bot_diagnostics(ts)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_diag_chat ON bot_diagnostics(chat_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_diag_status ON bot_diagnostics(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_diag_event ON bot_diagnostics(event_type)")
        log.info("✅ Система телеметрии MOXXI инициализирована.")
    except Exception as e:
        log.error("Ошибка инициализации телеметрии: %s", e)


async def _flush_batch() -> None:
    """Сбрасывает накопленные логи из очереди в SQLite одной транзакцией."""
    if not _log_queue:
        return
    batch = []
    while _log_queue and len(batch) < 100:
        batch.append(_log_queue.popleft())

    if not batch:
        return

    sql = """
    INSERT INTO bot_diagnostics (
        ts, dt, event_type, status, chat_id, chat_title, thread_id,
        user_id, username, user_name, command_key, full_text,
        reason, stack_trace, execution_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = [
        (
            item["ts"], item["dt"], item["event_type"], item["status"],
            item["chat_id"], item["chat_title"], item["thread_id"],
            item["user_id"], item["username"], item["user_name"],
            item["command_key"], item["full_text"],
            item["reason"], item["stack_trace"], item["execution_ms"]
        )
        for item in batch
    ]
    try:
        await db.executemany(sql, params)
    except Exception as e:
        log.warning("Не удалось записать пачку телеметрии: %s", e)


async def telemetry_worker(bot: Any = None) -> None:
    """Фоновый воркер: периодически сбрасывает логи и очищает старые записи."""
    log.info("🚀 Запущен фоновый воркер телеметрии MOXXI.")
    last_cleanup = time.time()
    while True:
        try:
            await _flush_batch()
            now = time.time()
            if now - last_cleanup > _CLEANUP_INTERVAL_SEC:
                last_cleanup = now
                cutoff = int(now - (_RETENTION_DAYS * 86400))
                try:
                    await db.execute("DELETE FROM bot_diagnostics WHERE ts < ?", (cutoff,))
                    log.info("Телеметрия: старые записи (старше %d дн.) очищены.", _RETENTION_DAYS)
                except Exception as e_clean:
                    log.warning("Ошибка очистки старой телеметрии: %s", e_clean)
        except asyncio.CancelledError:
            # Сбрасываем остаток перед выходом
            await _flush_batch()
            break
        except Exception as e:
            log.warning("Ошибка в telemetry_worker: %s", e)
        await asyncio.sleep(1.0)


def _enqueue_event(data: dict[str, Any]) -> None:
    """Добавляет событие в очередь. Если воркер не запущен, планирует одиночную запись."""
    if len(_log_queue) >= _MAX_QUEUE_SIZE:
        _log_queue.popleft()  # вытесняем самое старое при переполнении
    _log_queue.append(data)


# -------------------------------------------------------------------------
# Методы для регистрации событий
# -------------------------------------------------------------------------

async def log_command_success(event: Message, key: str, execution_ms: int = 0) -> None:
    """Успешно выполненная команда."""
    now = int(time.time())
    chat = getattr(event, "chat", None)
    user = getattr(event, "from_user", None)
    text = getattr(event, "text", "") or getattr(event, "caption", "") or ""

    _enqueue_event({
        "ts": now,
        "dt": _get_dt_str(now),
        "event_type": "cmd",
        "status": "ok",
        "chat_id": chat.id if chat else 0,
        "chat_title": (getattr(chat, "title", None) or getattr(chat, "username", None) or "Личные сообщения")[:100],
        "thread_id": getattr(event, "message_thread_id", None),
        "user_id": user.id if user else 0,
        "username": getattr(user, "username", "") or "",
        "user_name": (getattr(user, "first_name", "") or "Пользователь")[:100],
        "command_key": key[:50],
        "full_text": _clean_text(text),
        "reason": "",
        "stack_trace": "",
        "execution_ms": execution_ms,
    })


async def log_command_error(event: Message, key: str, err: Exception, execution_ms: int = 0) -> None:
    """Команда завершилась ошибкой."""
    now = int(time.time())
    chat = getattr(event, "chat", None)
    user = getattr(event, "from_user", None)
    text = getattr(event, "text", "") or getattr(event, "caption", "") or ""
    tb = traceback.format_exc()
    if not tb or "NoneType" in tb:
        tb = f"{type(err).__name__}: {err}"

    _enqueue_event({
        "ts": now,
        "dt": _get_dt_str(now),
        "event_type": "error",
        "status": "error",
        "chat_id": chat.id if chat else 0,
        "chat_title": (getattr(chat, "title", None) or getattr(chat, "username", None) or "Личные сообщения")[:100],
        "thread_id": getattr(event, "message_thread_id", None),
        "user_id": user.id if user else 0,
        "username": getattr(user, "username", "") or "",
        "user_name": (getattr(user, "first_name", "") or "Пользователь")[:100],
        "command_key": key[:50],
        "full_text": _clean_text(text),
        "reason": f"{type(err).__name__}: {str(err)[:250]}",
        "stack_trace": _clean_text(tb, 3000),
        "execution_ms": execution_ms,
    })


async def log_command_blocked(event: Message, key: str, block_type: str, reason: str) -> None:
    """Команда или действие заблокировано (не та тема, нет анкеты, ранг, спам)."""
    now = int(time.time())
    chat = getattr(event, "chat", None)
    user = getattr(event, "from_user", None)
    text = getattr(event, "text", "") or getattr(event, "caption", "") or ""

    _enqueue_event({
        "ts": now,
        "dt": _get_dt_str(now),
        "event_type": "block",
        "status": "blocked",
        "chat_id": chat.id if chat else 0,
        "chat_title": (getattr(chat, "title", None) or getattr(chat, "username", None) or "Личные сообщения")[:100],
        "thread_id": getattr(event, "message_thread_id", None),
        "user_id": user.id if user else 0,
        "username": getattr(user, "username", "") or "",
        "user_name": (getattr(user, "first_name", "") or "Пользователь")[:100],
        "command_key": key[:50],
        "full_text": _clean_text(text),
        "reason": f"[{block_type}] {reason}"[:250],
        "stack_trace": "",
        "execution_ms": 0,
    })


async def log_unhandled_error(event: ErrorEvent) -> None:
    """Глобальный перехватчик неожиданных ошибок aiogram."""
    now = int(time.time())
    err = event.exception
    tb = traceback.format_exc() if err else ""
    if not tb:
        tb = f"{type(err).__name__}: {err}"

    chat_id = 0
    chat_title = ""
    thread_id = None
    user_id = 0
    username = ""
    user_name = ""
    full_text = ""

    # Извлекаем контекст из Update
    upd = event.update
    msg: Optional[Message] = getattr(upd, "message", None) or getattr(upd, "edited_message", None)
    cq = getattr(upd, "callback_query", None)

    if msg:
        chat_id = msg.chat.id
        chat_title = getattr(msg.chat, "title", "") or ""
        thread_id = getattr(msg, "message_thread_id", None)
        if msg.from_user:
            user_id = msg.from_user.id
            username = msg.from_user.username or ""
            user_name = msg.from_user.first_name or ""
        full_text = msg.text or msg.caption or ""
    elif cq:
        if cq.message:
            chat_id = cq.message.chat.id
            chat_title = getattr(cq.message.chat, "title", "") or ""
            thread_id = getattr(cq.message, "message_thread_id", None)
        if cq.from_user:
            user_id = cq.from_user.id
            username = cq.from_user.username or ""
            user_name = cq.from_user.first_name or ""
        full_text = f"Callback: {cq.data or ''}"

    _enqueue_event({
        "ts": now,
        "dt": _get_dt_str(now),
        "event_type": "error",
        "status": "error",
        "chat_id": chat_id,
        "chat_title": chat_title[:100],
        "thread_id": thread_id,
        "user_id": user_id,
        "username": username,
        "user_name": user_name[:100],
        "command_key": "unhandled",
        "full_text": _clean_text(full_text),
        "reason": f"Unhandled: {type(err).__name__}: {str(err)[:250]}",
        "stack_trace": _clean_text(tb, 3000),
        "execution_ms": 0,
    })


# -------------------------------------------------------------------------
# Генерация сводок и аналитических отчётов
# -------------------------------------------------------------------------

async def get_diagnostics_summary(hours: int = 24, chat_id: Optional[int] = None) -> dict[str, Any]:
    """Сбор статистики за последние N часов."""
    # Сначала сбрасываем свежие записи в базу
    await _flush_batch()

    since_ts = int(time.time() - (hours * 3600))
    where_chat = "AND chat_id = ?" if chat_id else ""
    chat_params = [since_ts, chat_id] if chat_id else [since_ts]

    # 1. Общие счетчики
    row_counts = await db.fetchone(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_count,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
            AVG(CASE WHEN execution_ms > 0 THEN execution_ms ELSE NULL END) as avg_ms,
            MAX(execution_ms) as max_ms
        FROM bot_diagnostics 
        WHERE ts >= ? {where_chat}
    """, tuple(chat_params))

    total = row_counts["total"] if row_counts and row_counts["total"] else 0
    ok_count = row_counts["ok_count"] if row_counts and row_counts["ok_count"] else 0
    blocked_count = row_counts["blocked_count"] if row_counts and row_counts["blocked_count"] else 0
    error_count = row_counts["error_count"] if row_counts and row_counts["error_count"] else 0
    avg_ms = round(row_counts["avg_ms"] or 0, 1) if row_counts else 0.0
    max_ms = row_counts["max_ms"] or 0 if row_counts else 0

    # 2. Топ команд
    top_cmds = await db.fetchall(f"""
        SELECT command_key, COUNT(*) as cnt 
        FROM bot_diagnostics 
        WHERE ts >= ? AND status = 'ok' {where_chat}
        GROUP BY command_key 
        ORDER BY cnt DESC LIMIT 5
    """, tuple(chat_params))

    # 3. Причины блокировок / почему не ответил
    top_blocks = await db.fetchall(f"""
        SELECT reason, COUNT(*) as cnt 
        FROM bot_diagnostics 
        WHERE ts >= ? AND status = 'blocked' {where_chat}
        GROUP BY reason 
        ORDER BY cnt DESC LIMIT 5
    """, tuple(chat_params))

    # 4. Самые частые ошибки
    top_errors = await db.fetchall(f"""
        SELECT reason, COUNT(*) as cnt 
        FROM bot_diagnostics 
        WHERE ts >= ? AND status = 'error' {where_chat}
        GROUP BY reason 
        ORDER BY cnt DESC LIMIT 5
    """, tuple(chat_params))

    # 5. Топ активных чатов
    top_chats = []
    if not chat_id:
        top_chats = await db.fetchall("""
            SELECT chat_id, chat_title, COUNT(*) as cnt,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errs,
                   SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocks
            FROM bot_diagnostics 
            WHERE ts >= ?
            GROUP BY chat_id 
            ORDER BY cnt DESC LIMIT 5
        """, (since_ts,))

    # 6. Последние 5 ошибок с деталями
    recent_errors = await db.fetchall(f"""
        SELECT dt, chat_title, user_name, full_text, reason, stack_trace
        FROM bot_diagnostics
        WHERE ts >= ? AND status = 'error' {where_chat}
        ORDER BY id DESC LIMIT 5
    """, tuple(chat_params))

    return {
        "hours": hours,
        "total": total,
        "ok_count": ok_count,
        "blocked_count": blocked_count,
        "error_count": error_count,
        "avg_ms": avg_ms,
        "max_ms": max_ms,
        "top_cmds": top_cmds or [],
        "top_blocks": top_blocks or [],
        "top_errors": top_errors or [],
        "top_chats": top_chats or [],
        "recent_errors": recent_errors or [],
    }


def format_daily_summary_html(summary: dict[str, Any]) -> str:
    """Форматирует красивую HTML-сводку для отправки в Telegram."""
    hours = summary["hours"]
    total = summary["total"]
    ok_cnt = summary["ok_count"]
    blocked = summary["blocked_count"]
    errors = summary["error_count"]
    avg_ms = summary["avg_ms"]

    health_icon = "🟢" if errors == 0 else ("🟡" if errors < 5 else "🔴")
    rate = round((ok_cnt / total * 100), 1) if total > 0 else 100.0

    lines = [
        f"{health_icon} <b>БОРТОВОЙ ЖУРНАЛ MOXXI (за {hours} ч.)</b>",
        f"📅 <i>Время отчёта: {datetime.now(timezone(timedelta(hours=3))).strftime('%d.%m.%Y %H:%M')} МСК</i>\n",
        f"📊 <b>Всего событий:</b> <code>{total}</code>",
        f"✅ <b>Успешных команд:</b> <code>{ok_cnt}</code> ({rate}%)",
        f"⏱ <b>Средний отклик:</b> <code>{avg_ms} мс</code>",
        f"🚫 <b>Отклонено / блокировок:</b> <code>{blocked}</code>",
        f"🔴 <b>Ошибок / сбоев:</b> <code>{errors}</code>\n",
    ]

    # Топ команд
    if summary["top_cmds"]:
        lines.append("🏆 <b>Топ команд:</b>")
        for row in summary["top_cmds"]:
            lines.append(f"  • <code>{html.escape(row['command_key'])}</code> — {row['cnt']} раз")
        lines.append("")

    # Блокировки / почему бот не ответил
    if summary["top_blocks"]:
        lines.append("⚠️ <b>Где бот не ответил (блокировки):</b>")
        for row in summary["top_blocks"]:
            r = html.escape(row["reason"] or "Без причины")
            lines.append(f"  • <b>{row['cnt']}x</b>: <i>{r}</i>")
        lines.append("")

    # Ошибки
    if summary["top_errors"]:
        lines.append("🚨 <b>Основные ошибки за день:</b>")
        for row in summary["top_errors"]:
            r = html.escape(row["reason"] or "Неизвестная ошибка")
            lines.append(f"  • <b>{row['cnt']}x</b>: <code>{r}</code>")
        lines.append("")

    # Топ чатов
    if summary["top_chats"]:
        lines.append("💬 <b>Топ групп по нагрузке:</b>")
        for row in summary["top_chats"]:
            title = html.escape(row["chat_title"] or f"Чат {row['chat_id']}")
            lines.append(f"  • <b>{title}</b>: {row['cnt']} ком. (сбоев: {row['errs']}, блоков: {row['blocks']})")
        lines.append("")

    # Быстрые подсказки
    if errors == 0 and blocked == 0:
        lines.append("✨ <i>Все системы работают стабильно, сбоев не зафиксировано.</i>")
    elif errors > 0:
        lines.append("💡 <i>Чтобы увидеть точные строки и текст сообщений с ошибками:</i> <code>диагностика ошибки</code>")
    elif blocked > 0:
        lines.append("💡 <i>Чтобы изучить подробности блокировок:</i> <code>диагностика отказы</code>")

    return "\n".join(lines)


async def format_errors_detail_html(hours: int = 24, limit: int = 10) -> str:
    """Подробный отчёт по последним ошибкам с текстом сообщений."""
    await _flush_batch()
    since_ts = int(time.time() - (hours * 3600))
    rows = await db.fetchall("""
        SELECT dt, chat_title, user_name, user_id, full_text, reason, stack_trace
        FROM bot_diagnostics
        WHERE ts >= ? AND status = 'error'
        ORDER BY id DESC LIMIT ?
    """, (since_ts, limit))

    if not rows:
        return "✅ <b>За последние 24 часа критических ошибок не зафиксировано!</b>"

    lines = [f"🚨 <b>ПОСЛЕДНИЕ {len(rows)} ОШИБОК (за {hours} ч.):</b>\n"]
    for i, r in enumerate(rows, 1):
        dt = r["dt"]
        chat = html.escape(r["chat_title"] or "ЛС")
        user = html.escape(r["user_name"] or str(r["user_id"]))
        msg_text = html.escape(r["full_text"] or "(пусто)")
        reason = html.escape(r["reason"] or "")
        
        # Берём последние 2 значимые строки трейса
        st = r["stack_trace"] or ""
        st_lines = [l.strip() for l in st.split("\n") if l.strip()]
        short_st = html.escape("\n".join(st_lines[-2:])) if st_lines else ""

        lines.append(
            f"<b>#{i} [{dt}]</b> в <b>{chat}</b> от <b>{user}</b>\n"
            f"💬 <b>Текст:</b> <code>{msg_text}</code>\n"
            f"⚠️ <b>Ошибка:</b> <code>{reason}</code>\n"
            + (f"📍 <b>Стек:</b>\n<pre>{short_st}</pre>\n" if short_st else "\n")
        )

    return "\n".join(lines)


async def format_blocks_detail_html(hours: int = 24, limit: int = 15) -> str:
    """Подробный отчёт по блокировкам (где бот отказался отвечать)."""
    await _flush_batch()
    since_ts = int(time.time() - (hours * 3600))
    rows = await db.fetchall("""
        SELECT dt, chat_title, user_name, user_id, full_text, reason
        FROM bot_diagnostics
        WHERE ts >= ? AND status = 'blocked'
        ORDER BY id DESC LIMIT ?
    """, (since_ts, limit))

    if not rows:
        return "✅ <b>Блокировок и отказов за последние 24 часа нет!</b>"

    lines = [f"🚫 <b>ПОСЛЕДНИЕ {len(rows)} ОТКАЗОВ / БЛОКИРОВОК (за {hours} ч.):</b>\n"]
    for i, r in enumerate(rows, 1):
        dt = r["dt"]
        chat = html.escape(r["chat_title"] or "ЛС")
        user = html.escape(r["user_name"] or str(r["user_id"]))
        msg_text = html.escape(r["full_text"] or "(пусто)")
        reason = html.escape(r["reason"] or "Заблокировано")

        lines.append(
            f"<b>#{i} [{dt}]</b> в <b>{chat}</b> (👤 {user})\n"
            f"💬 <b>Сообщение:</b> <code>{msg_text}</code>\n"
            f"📌 <b>Причина:</b> <i>{reason}</i>\n"
        )

    return "\n".join(lines)


async def export_full_logs_txt(hours: int = 24, chat_id: Optional[int] = None) -> str:
    """Экспорт полного журнала событий в текстовый файл."""
    await _flush_batch()
    since_ts = int(time.time() - (hours * 3600))
    where_chat = "AND chat_id = ?" if chat_id else ""
    chat_params = [since_ts, chat_id] if chat_id else [since_ts]

    rows = await db.fetchall(f"""
        SELECT dt, status, event_type, chat_id, chat_title, thread_id,
               user_id, user_name, command_key, full_text, reason, execution_ms
        FROM bot_diagnostics
        WHERE ts >= ? {where_chat}
        ORDER BY id ASC
    """, tuple(chat_params))

    lines = [
        f"=== MOXXI FULL LOG EXPORT (Период: {hours} ч. | Всего записей: {len(rows)}) ===",
        f"Экспортировано: {_get_dt_str()} МСК\n"
    ]
    for r in rows:
        status_tag = f"[{r['status'].upper()}]"
        dur = f" ({r['execution_ms']}ms)" if r['execution_ms'] else ""
        thread_info = f" [topic:{r['thread_id']}]" if r['thread_id'] else ""
        lines.append(
            f"{r['dt']} {status_tag}{dur} | Чат: {r['chat_title']} ({r['chat_id']}){thread_info} | "
            f"Юзер: {r['user_name']} ({r['user_id']}) | Команда: {r['command_key']}\n"
            f"  Текст: {r['full_text']}\n"
            + (f"  Инфо: {r['reason']}\n" if r['reason'] else "")
            + "-" * 70
        )

    return "\n".join(lines)
