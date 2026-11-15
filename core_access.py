"""ДК — «Доступ команд»: гибкая настройка прав на каждую команду.

Логика проверки для команды `key` в чате:
  1. если команда отключена (enabled=0) — молча игнорируем;
  2. если задан личный доступ (cmd_personal) — пользователю можно всегда;
  3. если задан свой ранг (cmd_access.rank) — сравниваем с ним;
  4. иначе — базовый ранг команды из реестра.
"""
from __future__ import annotations

import time
from typing import Optional

import db
from core_ranks import effective_rank, rank_label

# кэш настроек: {chat_id: {cmd: (rank, enabled)}}
_cache: dict[int, dict[str, tuple[int, int]]] = {}
_personal: dict[int, dict[tuple[str, int], str]] = {}


def invalidate(chat_id: int) -> None:
    _cache.pop(chat_id, None)
    _personal.pop(chat_id, None)


async def _load(chat_id: int) -> dict[str, tuple[int, int]]:
    if chat_id not in _cache:
        rows = await db.fetchall(
            "SELECT cmd, rank, enabled FROM cmd_access WHERE chat_id=?", (chat_id,))
        _cache[chat_id] = {r["cmd"]: (int(r["rank"]), int(r["enabled"])) for r in rows}
    return _cache[chat_id]


async def _load_personal(chat_id: int) -> dict[tuple[str, int], str]:
    if chat_id not in _personal:
        rows = await db.fetchall(
            "SELECT cmd, user_id, mode FROM cmd_personal WHERE chat_id=?", (chat_id,))
        _personal[chat_id] = {(r["cmd"], r["user_id"]): (r["mode"] or "allow") for r in rows}
    return _personal[chat_id]


async def required_rank(chat_id: int, key: str, base: int) -> tuple[int, bool]:
    """-> (нужный_ранг, включена_ли_команда)"""
    conf = await _load(chat_id)
    if key in conf:
        rank, enabled = conf[key]
        return rank, bool(enabled)
    return base, True


async def check(message, bot, key: str, base_rank: int,
                had_prefix: bool = True) -> Optional[str]:
    """None — можно выполнять. Иначе текст отказа ('' = молча проигнорировать)."""
    chat = message.chat
    if chat.type == "private":
        return None

    import config
    uid = message.from_user.id if message.from_user else 0
    if uid and config.is_bot_owner(uid):
        return None

    need, enabled = await required_rank(chat.id, key, base_rank)
    if not enabled:
        return ""  # команда выключена в этом чате — тихо игнорируем

    pers = await _load_personal(chat.id)
    mode = pers.get((key, uid)) if uid else None

    # −ЛДК: команда отобрана лично у человека
    if mode == "deny":
        from core_registry import MAX_RANK
        have = await effective_rank(message, bot)
        if have < MAX_RANK:      # у лидера отобрать нельзя
            quiet = await db.get_setting(chat.id, "dk_silent", "0") == "1"
            return "" if quiet else (
                "🔒 У вас <b>отобран</b> доступ к этой команде.\n"
                "Вернуть может админ: <code>+лдк @вы команда</code>")

    if mode == "allow":
        return None              # +ЛДК: выдан личный доступ

    if need <= 0:
        return None

    have = await effective_rank(message, bot)
    if have >= need:
        return None

    # Случайные разговорные фразы без префикса («спасибо», «кто», «дать» и т.п.) пропускаем молча
    from core_registry import EXPLICIT_ADDRESS_NAMES
    if not had_prefix and key in EXPLICIT_ADDRESS_NAMES:
        return ""

    ADMIN_KEYS = {"повысить", "+модер", "понизить", "-модер", "снять", "кик", "бан", "мут", "варн", "дк", "чистка"}
    # Обычный разговор от участников без ранга не спамит ошибками на простые команды
    if not had_prefix and have == 0 and key not in ADMIN_KEYS:
        return ""

    quiet = await db.get_setting(chat.id, "dk_silent", "0") == "1"
    if quiet and key not in ADMIN_KEYS:
        return ""

    cmd_name = (key or "этой команды").strip()
    return (
        f"⛔️ <b>Недостаточно прав для команды «{cmd_name}»!</b>\n\n"
        f"🔒 Требуемый ранг: <b>{rank_label(need)}</b> (Ранг {need})\n"
        f"👤 Ваш текущий ранг: <b>{rank_label(have) if have else 'Участник'}</b> (Ранг {have})\n\n"
        f"💡 <b>Как настроить доступ к этой команде:</b>\n"
        f"• Разрешить команду всем: <code>дк {cmd_name} 0</code>\n"
        f"• Изменить ранг доступа: <code>дк {cmd_name} {need}</code>\n"
        f"• Выдать личный доступ игроку: <code>+пдк @юзер {cmd_name}</code>\n\n"
        f"ℹ️ <i>Если вы участник — обратитесь к администрации чата с просьбой открыть команду:</i> <code>дк {cmd_name} 0</code>"
    )


try:
    from h_rp import ACTIONS as _RP_ACTIONS, ALIASES as _RP_ALIASES
    _RP_KEYS = set(_RP_ACTIONS.keys()) | set(_RP_ALIASES.keys()) | {"рп", "рп команды", "действия", "рп статистика", "статистика рп"}
except Exception:
    _RP_KEYS = set()

ALLOWED_WITHOUT_FORM = {
    "описание", "+описание", "шаблон", "анкета", "инфа", "команды", "ид",
    "мой ранг", "правила", "меню", "найти", "справка", "кто я", "профиль", "мой профиль",
    "никлист", "описаниелист", "ник", "+ник", "-ник", "статус", "бот",
    "пол", "мой пол", "сменить пол", "выбрать пол", "дизайн",
} | _RP_KEYS


async def form_gate(message, bot) -> bool:
    """True — сообщение пропускаем. False — участник не заполнил анкету."""
    try:
        chat = message.chat
        if chat.type == "private":
            return True
        if not message.from_user or message.from_user.is_bot:
            return True

        from h_userinfo import needs_form
        if not await needs_form(chat.id, message.from_user.id):
            return True

        # модерация не блокируется
        from core_ranks import effective_rank
        if await effective_rank(message, bot) >= 1:
            return True
        return False
    except Exception:
        return True


async def access_middleware(handler, event, data: dict):
    """Применяет ДК и антифлуд до вызова хэндлера."""
    key = data.get("cmd_key")
    if key:
        import logging
        logging.getLogger("moxxibot").info("🎯 [КОМАНДА РАСПОЗНАНА] key=%r rank=%r had_prefix=%s text=%r",
                                           key, data.get("cmd_rank"), data.get("had_prefix"), getattr(event, "text", None))
        # антифлуд: защита от перегрузки в больших чатах
        import core_throttle as throttle
        uid = event.from_user.id if event.from_user else 0
        if uid and not throttle.check(uid):
            try:
                import core_telemetry as telemetry
                await telemetry.log_command_blocked(event, key, "antiflood", "Слишком много команд подряд (троттлинг)")
            except Exception:
                pass
            if throttle.should_warn(uid):
                try:
                    await event.reply("⏳ Слишком много команд подряд. "
                                      "Подождите несколько секунд.")
                except Exception:
                    pass
            return
        bot = data.get("bot")
        verdict = await check(event, bot, key, int(data.get("cmd_rank") or 0),
                              bool(data.get("had_prefix", True)))
        if verdict is not None:
            try:
                import core_telemetry as telemetry
                await telemetry.log_command_blocked(event, key, "perm_denied", verdict or "Недостаточно прав (ранг/ДК)")
            except Exception:
                pass
            if verdict:
                try:
                    await event.reply(verdict)
                except Exception:
                    pass
            return

        # Изоляция темы описаний: разрешены только анкеты, ники, бот и модерация
        if getattr(event, "chat", None) and event.chat.type in ("group", "supergroup"):
            from h_userinfo import get_form_topic, topic_id
            form_top = await get_form_topic(event.chat.id)
            if form_top and form_top > 0 and topic_id(event) == form_top:
                ALLOWED_IN_FORM_TOPIC = {
                    "описание", "+описание", "шаблон", "анкета", "мое описание", "моё описание",
                    "ник", "+ник", "-ник", "поставить ник", "снять ник",
                    "бот", "мокси", "статус", "bot", "status",
                    "бан", "кик", "мут", "варн", "пред", "разбан", "размут", "снять пред",
                    "чек", "амнистия", "ограничить"
                }
                if key not in ALLOWED_IN_FORM_TOPIC:
                    try:
                        sent = await event.reply(
                            "📝 В теме описаний разрешены только анкеты, ники и модерация.\n"
                            "Для остальных команд перейдите в темы общения!"
                        )
                        from h_userinfo import _autodel
                        _autodel(sent, 20)
                    except Exception:
                        pass
                    return

        # незаполнившим анкету доступны только базовые команды
        if key not in ALLOWED_WITHOUT_FORM:
            bot = data.get("bot")
            try:
                gate_ok = await form_gate(event, bot)
            except Exception:
                gate_ok = True
            if not gate_ok:
                try:
                    import core_telemetry as telemetry
                    await telemetry.log_command_blocked(event, key, "form_gate", "Участник не заполнил описание/анкету")
                except Exception:
                    pass
                msg = "📝 Сначала заполните описание — напишите команду <code>шаблон</code> прямо здесь!"
                try:
                    await event.reply(msg, disable_web_page_preview=True)
                except Exception:
                    try:
                        await event.answer(msg, disable_web_page_preview=True)
                    except Exception:
                        pass
                return


        # доступ разрешён на уровне ДК — внутренние require() не должны спорить
        try:
            object.__setattr__(event, "_dk_ok", True)
        except Exception:
            pass
        if event.from_user:
            try:
                await db.track_daily_activity(event.from_user.id, action="cmd", is_group=(event.chat.type != "private"))
            except Exception:
                pass

        # Выполнение команды с замером времени и полным логированием
        t0 = time.monotonic()
        try:
            res = await handler(event, data)
            dur_ms = int((time.monotonic() - t0) * 1000)
            try:
                import core_telemetry as telemetry
                await telemetry.log_command_success(event, key, dur_ms)
            except Exception:
                pass
            return res
        except Exception as e:
            dur_ms = int((time.monotonic() - t0) * 1000)
            try:
                import core_telemetry as telemetry
                await telemetry.log_command_error(event, key, e, dur_ms)
            except Exception:
                pass
            raise
    return await handler(event, data)
