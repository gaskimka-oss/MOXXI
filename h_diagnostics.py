"""Модуль диагностики и бортового журнала MOXXI (MOXXI Health & Diagnostics).

Позволяет создателям и администрации бота:
1. Просматривать ежедневную сводку: сколько команд выполнено, где бот не ответил, какие были ошибки.
2. Изучать подробные логи с полным текстом сообщений пользователей и стеком ошибок.
3. Экспортировать полные логи за сутки в файл для совместного анализа.
"""
from __future__ import annotations

import io
import logging
from aiogram import Bot, F, Router
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
import db
from core_registry import Cmd
import core_telemetry as telemetry

log = logging.getLogger("moxxibot.diagnostics")
router = Router(name="diagnostics")

S_DIAG = 45


async def _has_access(message_or_cq: Message | CallbackQuery) -> bool:
    """Доступ разрешён владельцам бота и администраторам стаффа."""
    u = message_or_cq.from_user
    if not u:
        return False
    if config.is_bot_owner(u.id):
        return True
    try:
        rank = await db.get_bot_staff_rank(u.id)
        if rank >= 3:
            return True
    except Exception:
        pass
    return False


def _get_diag_kb(hours: int = 24) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для быстрого переключения между отчётами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"diag:sum:{hours}"),
            InlineKeyboardButton(text="🚨 Ошибки", callback_data=f"diag:err:{hours}"),
        ],
        [
            InlineKeyboardButton(text="🚫 Блокировки / Отказы", callback_data=f"diag:blk:{hours}"),
            InlineKeyboardButton(text="📥 Экспорт логов (.txt)", callback_data=f"diag:exp:{hours}"),
        ],
        [
            InlineKeyboardButton(text="⏱ За 12ч", callback_data="diag:sum:12"),
            InlineKeyboardButton(text="⏱ За 24ч", callback_data="diag:sum:24"),
            InlineKeyboardButton(text="⏱ За 48ч", callback_data="diag:sum:48"),
        ]
    ])


@router.message(Cmd("диагностика", "лог дня", "логи дня", "отчет дня", "health",
                    section=S_DIAG, rank=0,
                    usage="диагностика [ошибки|отказы|экспорт|часы]",
                    desc="Бортовой журнал и диагностика здоровья бота за день"))
async def cmd_diagnostics(message: Message, bot: Bot, args: str = "", **kw):
    """Команда просмотра диагностики за день."""
    if not await _has_access(message):
        return

    sub = (args or "").strip().lower()
    parts = sub.split()
    first_arg = parts[0] if parts else ""
    hours = 24

    # Проверка, передано ли число часов
    for p in parts:
        if p.isdigit():
            h_val = int(p)
            if 1 <= h_val <= 168:
                hours = h_val

    # 1. Запрос ошибок
    if first_arg in ("ошибки", "ошибка", "errors", "err"):
        text = await telemetry.format_errors_detail_html(hours=hours, limit=10)
        return await message.reply(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)

    # 2. Запрос блокировок
    if first_arg in ("отказы", "блокировки", "блоки", "blocks", "blk"):
        text = await telemetry.format_blocks_detail_html(hours=hours, limit=15)
        return await message.reply(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)

    # 3. Экспорт полного лога в файл
    if first_arg in ("экспорт", "файл", "export", "dump"):
        log_text = await telemetry.export_full_logs_txt(hours=hours)
        file_bytes = log_text.encode("utf-8")
        filename = f"moxxi_logs_{hours}h.txt"
        doc = BufferedInputFile(file_bytes, filename=filename)
        return await message.reply_document(
            doc,
            caption=f"📁 <b>Полный бортовой журнал MOXXI за последние {hours} ч.</b>\nВсего строк: {len(log_text.splitlines())}"
        )

    # 4. Общая сводка
    summary = await telemetry.get_diagnostics_summary(hours=hours)
    text = telemetry.format_daily_summary_html(summary)
    await message.reply(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("diag:"))
async def on_diag_callback(cq: CallbackQuery, bot: Bot):
    """Инлайн-переключение вкладок диагностики."""
    if not await _has_access(cq):
        return await cq.answer("⛔️ Доступно только создателям бота.", show_alert=True)

    parts = cq.data.split(":")
    action = parts[1] if len(parts) > 1 else "sum"
    hours = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 24

    await cq.answer()

    if action == "sum":
        summary = await telemetry.get_diagnostics_summary(hours=hours)
        text = telemetry.format_daily_summary_html(summary)
        try:
            await cq.message.edit_text(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)
        except Exception:
            pass

    elif action == "err":
        text = await telemetry.format_errors_detail_html(hours=hours, limit=10)
        try:
            await cq.message.edit_text(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)
        except Exception:
            pass

    elif action == "blk":
        text = await telemetry.format_blocks_detail_html(hours=hours, limit=15)
        try:
            await cq.message.edit_text(text, reply_markup=_get_diag_kb(hours), disable_web_page_preview=True)
        except Exception:
            pass

    elif action == "exp":
        log_text = await telemetry.export_full_logs_txt(hours=hours)
        file_bytes = log_text.encode("utf-8")
        filename = f"moxxi_logs_{hours}h.txt"
        doc = BufferedInputFile(file_bytes, filename=filename)
        await cq.message.reply_document(
            doc,
            caption=f"📁 <b>Полный бортовой журнал MOXXI за последние {hours} ч.</b>"
        )
