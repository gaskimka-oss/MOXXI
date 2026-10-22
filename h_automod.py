"""Автомодерация: мут за оскорбления и мат. Словарь + ИИ-надзор."""
from __future__ import annotations

import html
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.types import ChatPermissions, Message

import db
import core_modlog as modlog
import core_toxicity as toxicity
from core_punish import log_punish
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import human_period, parse_period
from utils import mention, mention_id

router = Router(name="automod")
S = 3

MUTE_OFF = ChatPermissions(
    can_send_messages=False, can_send_audios=False, can_send_documents=False,
    can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
    can_send_voice_notes=False, can_send_polls=False,
    can_send_other_messages=False, can_add_web_page_previews=False)

# уровень -> (срок мута в секундах, подпись)
DEFAULT_ACTIONS = {
    1: (0, "предупреждение"),      # 0 = только варн, без мута
    2: (3600, "мут 1 час"),        # оскорбление
    3: (3600, "мут 1 час"),        # мат / угроза
}


async def is_enabled(chat_id: int) -> bool:
    return await db.get_setting(chat_id, "automod", "0") == "1"


async def get_mute_time(chat_id: int, level: int) -> int:
    v = await db.get_setting(chat_id, f"automod_time_{level}", "")
    if v.isdigit():
        return int(v)
    return DEFAULT_ACTIONS.get(level, (3600, ""))[0]


async def _delete_flag(chat_id: int) -> bool:
    return await db.get_setting(chat_id, "automod_delete", "1") == "1"


async def _autodel_msg(msg, delay: int = 5):
    try:
        import asyncio
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


def uid_self(message: Message) -> int:
    return message.from_user.id if message.from_user else 0


async def handle(message: Message, bot: Bot) -> bool:
    """Проверяет сообщение. True — нарушение обработано."""
    if message.chat.type == "private":
        return False
    if not message.from_user or message.from_user.is_bot:
        return False

    text = (message.text or message.caption or "").strip()
    if len(text) < 2:
        return False

    # модерацию не трогаем
    min_rank = int(await db.get_setting(message.chat.id, "automod_skip_rank", "1"))
    if await effective_rank(message, bot) >= min_rank:
        return False

    # 1. Проверка пользовательского чёрного списка запрещённых слов чата (+фильтр)
    filters = await db.get_filtered_words(message.chat.id)
    if filters:
        text_lower = text.lower()
        matched_word = None
        filter_action = "warn"
        for fw in filters:
            w = fw["word"].lower().strip()
            if w in text_lower:
                matched_word = w
                filter_action = fw.get("action") or "warn"
                break

        if matched_word:
            try:
                await message.delete()
            except Exception:
                pass

            uid = message.from_user.id
            import asyncio
            if filter_action == "mute":
                secs = 3600
                until = datetime.now(timezone.utc) + timedelta(seconds=secs)
                try:
                    await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
                except Exception:
                    pass
                await log_punish(message.chat.id, uid, "mute", f"фильтр слов: {matched_word}", secs, 0)
                notice = await message.answer(
                    f"🔇 {mention(message.from_user)} получил <b>мут на 1 час</b> за запрещённое слово!"
                )
            elif filter_action == "delete":
                notice = await message.answer(
                    f"🗑 Сообщение {mention(message.from_user)} удалено: содержит запрещённое слово из фильтра чата."
                )
            else:  # warn
                await db.execute(
                    "INSERT INTO warns (chat_id, user_id, reason, by_id, ts) VALUES (?,?,?,?,?)",
                    (message.chat.id, uid, f"запрещённое слово ({matched_word})", 0, int(time.time()))
                )
                await log_punish(message.chat.id, uid, "warn", f"фильтр слов: {matched_word}", 0, 0)
                notice = await message.answer(
                    f"⚠️ {mention(message.from_user)} получил <b>предупреждение</b> за запрещённое слово!"
                )
            asyncio.create_task(_autodel_msg(notice, 7))
            return True

    tid = message.message_thread_id or 0
    chat_on = await is_enabled(message.chat.id)
    topic_on = (await db.get_setting(message.chat.id, f"topic_automod_{tid}", "0") == "1")
    if not (chat_on or topic_on):
        return False

    # 2. Проверка тяжелейших оскорблений родных (мать, мамка и т.д.) — немедленный кик / бан!
    from h_community_support import detect_staff_abuse
    is_abuse, abuse_reason = detect_staff_abuse(text)
    if is_abuse and "родных" in abuse_reason.lower():
        try:
            await message.delete()
        except Exception:
            pass
        uid = message.from_user.id
        try:
            until_ban = datetime.now(timezone.utc) + timedelta(days=1)
            await bot.ban_chat_member(message.chat.id, uid, until_date=until_ban)
        except Exception:
            pass
        await log_punish(message.chat.id, uid, "ban", f"ИИ-автомодерация: {abuse_reason}", 86400, 0)
        notice = await message.answer(
            f"⛔️ 🤖 <b>ИИ-МОДЕРАЦИЯ: КИК / БАН</b>\n\n"
            f"👤 {mention(message.from_user)} был <b>исключён из чата (Бан 24ч)</b>!\n"
            f"📝 <b>Причина:</b> Оскорбление родных / недопустимое поведение\n"
            f"📜 <i>Соблюдайте правила чата (команда <code>правила</code>)!</i>"
        )
        import asyncio
        asyncio.create_task(_autodel_msg(notice, 15))
        return True

    use_ai = (await db.get_setting(message.chat.id, "automod_ai", "1") == "1") or topic_on
    strict = (await db.get_setting(message.chat.id, "automod_strict", "1") == "1") or topic_on
    addressed = bool(message.reply_to_message and message.reply_to_message.from_user
                     and message.reply_to_message.from_user.id != uid_self(message))
    ai_ctx = ""
    if use_ai:
        try:
            import core_ai as _ai
            if _ai.available():
                ai_ctx = await modlog.build_context(message.chat.id,
                                                    message.from_user.id, text)
        except Exception:
            pass
    level, reason, source = await toxicity.check(
        text, use_ai=use_ai, addressed=addressed, punish_soft_mat=strict,
        context=ai_ctx)

    if is_abuse and level < 2:
        level = 2
        reason = abuse_reason or "нецензурная брань"

    if level < 2:
        return False

    uid = message.from_user.id
    try:
        await message.delete()
    except Exception:
        pass

    # Фиксируем варн в базе данных
    await db.execute(
        "INSERT INTO warns (chat_id, user_id, admin_id, reason, ts) VALUES (?,?,?,?,?)",
        (message.chat.id, uid, 0, f"ИИ: {reason}", int(time.time()))
    )
    row = await db.fetchone("SELECT COUNT(*) c FROM warns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
    warn_cnt = int(row["c"]) if row else 1

    import asyncio
    # Если набрано 3 или более варнов — автоматический БАН / КИК из чата!
    if warn_cnt >= 3:
        try:
            until_ban = datetime.now(timezone.utc) + timedelta(days=1)
            await bot.ban_chat_member(message.chat.id, uid, until_date=until_ban)
        except Exception:
            pass
        await db.execute("DELETE FROM warns WHERE chat_id=? AND user_id=?", (message.chat.id, uid))
        await log_punish(message.chat.id, uid, "ban", f"ИИ: лимит 3/3 варнов ({reason})", 86400, 0)
        notice = await message.answer(
            f"🚫 🤖 <b>ИИ-МОДЕРАЦИЯ: ИСКЛЮЧЕНИЕ / БАН</b>\n\n"
            f"👤 {mention(message.from_user)} превысил лимит предупреждений: <b>[ 🟥 🟥 🟥 ] (3/3)</b>!\n"
            f"⚡️ <b>Применено:</b> Исключение из чата (Бан на 24 часа).\n"
            f"📝 <b>Последнее нарушение:</b> {html.escape(reason)}\n"
            f"📜 <i>Соблюдайте правила чата (команда <code>правила</code>)!</i>"
        )
        asyncio.create_task(_autodel_msg(notice, 20))
        return True

    # Иначе — выдаём Мут на 1 час + Предупреждение (Варн)
    secs = await get_mute_time(message.chat.id, level)
    if secs < 1800:
        secs = 3600
    until = datetime.now(timezone.utc) + timedelta(seconds=secs)
    try:
        await bot.restrict_chat_member(message.chat.id, uid, MUTE_OFF, until_date=until)
    except Exception:
        pass
    await db.execute(
        "INSERT INTO mutes (chat_id, user_id, reason, by_id, until, ts) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(chat_id, user_id) DO UPDATE SET "
        "reason=excluded.reason, until=excluded.until",
        (message.chat.id, uid, f"ИИ: {reason}", 0, int(time.time()) + secs, int(time.time()))
    )
    await log_punish(message.chat.id, uid, "mute", f"ИИ: {reason}", secs, 0)

    bar = " ".join("🟥" if i < warn_cnt else "⬜️" for i in range(3))
    notice = await message.answer(
        f"🛡 🤖 <b>ИИ-АВТОМОДЕРАЦИЯ MOXXI</b>\n\n"
        f"👤 {mention(message.from_user)}\n"
        f"⚠️ <b>Нарушение:</b> {html.escape(reason)}\n"
        f"⚡️ <b>Наказание:</b> 🔇 Мут на <b>{human_period(secs)}</b> + Предупреждение <b>[ {bar} ] ({warn_cnt}/3)</b>\n"
        f"🗑 <i>Сообщение удалено. При получении 3 варнов — автоматический бан!</i>"
    )
    asyncio.create_task(_autodel_msg(notice, 15))
    return True


# ═══════════════ НАСТРОЙКА ═══════════════
@router.message(Cmd("+автоправила", "-автоправила", "+автомут", "-автомут", "+ии модерация", "-ии модерация",
                    "+автомод", "-автомод", "автоправила", "автомут", "автомодерация", "антимат",
                    section=S, rank=0, group_only=False,
                    usage="+автоправила / +автомут [вкл|выкл]",
                    desc="🤖 ИИ-Автомодерация и автоправила темы (мут, варн, бан, кик)"))
async def cmd_automod(message: Message, bot: Bot, args: str = "", **kw):
    import config
    uid = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(uid) and not await require(message, bot, 3):
        return

    raw_cmd = (message.text or "").strip().lower()
    a = (args or "").strip().lower()
    cid = message.chat.id
    tid = message.message_thread_id or 0

    is_turn_off = (
        raw_cmd.startswith(("-автоправила", "-автомут", "-ии модерация", "-автомод")) or
        a in {"выкл", "off", "нет", "выключить", "0"}
    )
    is_turn_on = (
        raw_cmd.startswith(("+автоправила", "+автомут", "+ии модерация", "+автомод")) or
        a in {"вкл", "on", "да", "включить", "1"} or
        (not a and raw_cmd.startswith("+"))
    )

    if is_turn_off:
        await db.set_setting(cid, f"topic_automod_{tid}", "0")
        await db.set_setting(cid, "automod", "0")
        loc_str = f"в ветке #{tid}" if tid else "в этом чате"
        return await message.reply(f"🤖 <b>ИИ-Автомодерация и автоправила выключены</b> {loc_str}.")

    if is_turn_on or a in {"", "инфо"}:
        await db.set_setting(cid, "automod", "1")
        await db.set_setting(cid, "automod_ai", "1")
        await db.set_setting(cid, "automod_strict", "1")
        await db.set_setting(cid, f"topic_automod_{tid}", "1")
        await db.set_setting(cid, "topic_automod_thread_id", str(tid))

        import core_ai as ai
        brain = (f"🟢 <b>ИИ-надзор активен:</b> {ai.provider()}"
                 if ai.available() else
                 "⚪️ <b>ИИ-надзор:</b> работает встроенный словарь + фильтры")

        loc_str = f"темы общения (ветка #{tid})" if tid else "этого чата"
        return await message.reply(
            f"🛡 ✨ <b>ИИ-АВТОМОДЕРАЦИЯ И АВТОПРАВИЛА ВКЛЮЧЕНЫ!</b> ✨ 🛡\n"
            f"✦ ════════ • ⊰ 💖 🔮 ⚖️ 🤖 🍷 👑 ⊱ • ════════ ✦\n\n"
            f"📍 <b>Область действия:</b> {loc_str}\n"
            f"{brain}\n\n"
            f"⚡️ <b>Автоматическая лестница наказаний ИИ:</b>\n"
            f"• 🔇 <b>Мат / Оскорбления / Токсичность:</b> Удаление сообщения + Мут 1 час + Предупреждение;\n"
            f"• ⛔️ <b>Оскорбление родных / Скам / 18+:</b> Немедленный Кик / Бан на 24 часа;\n"
            f"• 🚫 <b>Накопление 3 варнов:</b> Автоматический Бан и исключение из беседы;\n"
            f"• 🛡 Модераторы (ранг 1+) защищены от ложных срабатываний.\n\n"
            f"🔒 <i>Выключить автомодерацию: <code>-автоправила</code> или <code>-автомут</code></i>"
        )

    # автомут время 2 часа
    if a.startswith("время"):
        secs, _ = parse_period(a[5:])
        if not secs:
            return await message.reply(
                "Формат: <code>автомут время 2 часа</code>\n"
                "Можно: 30 минут · 1 час · 1 день")
        await db.set_setting(cid, "automod_time_2", str(secs))
        await db.set_setting(cid, "automod_time_3", str(secs))
        return await message.reply(f"⏱ Срок автомута: <b>{human_period(secs)}</b>")

    # автомут тест <текст>
    if a.startswith("тест"):
        probe = (args or "")[4:].strip()
        if not probe:
            return await message.reply("Формат: <code>автомут тест ты дебил</code>")
        lvl, reason, src = await toxicity.check(probe)
        verdict = {0: "✅ чисто", 1: "🟡 грубость",
                   2: "🟠 оскорбление", 3: "🔴 мат/угроза"}[lvl]
        secs = await get_mute_time(cid, lvl) if lvl >= 2 else 0
        act = f"мут {human_period(secs)}" if secs else "без наказания"
        return await message.reply(
            f"🔍 <b>Проверка текста</b>\n\n"
            f"«{html.escape(probe[:120])}»\n\n"
            f"Вердикт: {verdict}\n"
            f"Причина: {html.escape(reason or '—')}\n"
            f"Источник: {src}\n"
            f"Действие: <b>{act}</b>")

    if a.startswith("ии"):
        import core_ai as ai
        val = "0" if "выкл" in a else "1"
        await db.set_setting(cid, "automod_ai", val)
        state = "включён" if val == "1" else "выключен"
        extra = ("" if ai.available() else
                 "\n\n⚠️ <i>Ключ ИИ не задан — пока работает только словарь. "
                 "Как включить: команда </i><code>ии</code>")
        return await message.reply(f"🧠 ИИ-надзор: <b>{state}</b>{extra}")

    if a.startswith("удаление"):
        val = "0" if "выкл" in a else "1"
        await db.set_setting(cid, "automod_delete", val)
        return await message.reply(
            f"🗑 Удаление сообщений: <b>{'включено' if val == '1' else 'выключено'}</b>")

    on = await is_enabled(cid)
    t2 = await get_mute_time(cid, 2)
    dele = await _delete_flag(cid)
    import core_ai as ai
    ai_on = await db.get_setting(cid, "automod_ai", "1") == "1"
    ai_txt = (f"🟢 {ai.provider()}" if ai.available() and ai_on
              else "🔴 выключен" if not ai_on
              else "⚪️ ключ не задан")
    await message.reply(
        f"🤖 <b>Автомодерация</b>\n\n"
        f"Состояние: <b>{'🟢 включена' if on else '🔴 выключена'}</b>\n"
        f"Срок мута: <b>{human_period(t2)}</b>\n"
        f"Удалять сообщение: <b>{'да' if dele else 'нет'}</b>\n"
        f"ИИ-надзор: <b>{ai_txt}</b>\n\n"
        f"<code>автомут вкл</code> — включить\n"
        f"<code>автомут выкл</code> — выключить\n"
        f"<code>автомут время 2 часа</code> — срок мута\n"
        f"<code>автомут тест текст</code> — проверить фразу\n"
        f"<code>автомут удаление выкл</code> — не удалять\n"
        f"<code>автомут ии выкл</code> — только словарь\n"
        f"<code>ии</code> — настройки ИИ-надзора")


@router.message(Cmd("нарушения", "лог автомута", section=S, rank=1,
                    usage="нарушения", desc="Последние срабатывания автомодерации"))
async def cmd_violations(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    rows = await db.fetchall(
        "SELECT p.*, u.first_name FROM punishments p "
        "LEFT JOIN users u ON u.user_id=p.user_id "
        "WHERE p.chat_id=? AND p.by_id=0 AND p.reason LIKE 'автомодерация%' "
        "ORDER BY p.id DESC LIMIT 15", (message.chat.id,))
    if not rows:
        return await message.reply("🤖 Автомодерация ещё не срабатывала.")
    lines = ["🤖 <b>Срабатывания автомодерации</b>\n"]
    for r in rows:
        lines.append(
            f"• {mention_id(r['user_id'], r['first_name'])} — "
            f"{html.escape((r['reason'] or '').replace('автомодерация: ', ''))}\n"
            f"   {time.strftime('%d.%m %H:%M', time.localtime(r['ts']))} · "
            f"<code>#{r['id']}</code>")
    await message.reply("\n".join(lines)[:3800], disable_web_page_preview=True)


@router.message(Cmd("автомут строгий", "строгий мат", section=S, rank=4,
                    usage="автомут строгий вкл|выкл",
                    desc="Наказывать мат даже без адресата"))
async def cmd_strict(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip().lower()
    if a in {"вкл", "on", "да"}:
        await db.set_setting(message.chat.id, "automod_strict", "1")
        return await message.reply(
            "🔴 <b>Строгий режим включён</b>\n\n"
            "Теперь наказывается любой мат, даже «бля» без адресата.")
    if a in {"выкл", "off", "нет"}:
        await db.set_setting(message.chat.id, "automod_strict", "0")
        return await message.reply(
            "🟢 <b>Строгий режим выключен</b>\n\n"
            "Мат-междометия («бля», «пиздец», «заебался») не наказываются.\n"
            "Наказывается только мат в адрес человека.")
    cur = await db.get_setting(message.chat.id, "automod_strict", "0")
    await message.reply(
        f"Строгий режим: <b>{'включён' if cur == '1' else 'выключен'}</b>\n\n"
        f"<i>Выключен — «бля» и «пиздец» без адресата пропускаются.</i>\n"
        f"Изменить: <code>автомут строгий вкл</code>")


# ═══════════════ ИИ-НАДЗОР ═══════════════
@router.message(Cmd("ии надзор", "ии статус", "автомут ии", "нейросеть статус", "ии настройки",
                    section=S, rank=6, usage="ии надзор", desc="🧠 ИИ-надзор: статус и настройка"))
async def cmd_ai(message: Message, bot: Bot, args: str = "", **kw):
    """Статус ИИ, включение оповещений."""
    if not await require(message, bot, 6):
        return
    import core_ai as ai
    cid = message.chat.id
    a = (args or "").strip().lower()

    # ии оповещения вкл|выкл
    if a.startswith(("оповещ", "уведом", "алерт")):
        val = "0" if "выкл" in a else "1"
        await db.set_setting(cid, "ai_alerts", val)
        return await message.reply(
            f"🔔 Оповещения о спорных наказаниях: "
            f"<b>{'включены' if val == '1' else 'выключены'}</b>")


@router.message(Cmd("ии сводка", "сводка чата", "отчет чата", section=S, rank=4,
                    usage="ии сводка", desc="📊 ИИ-сводка обстановки в чате"))
async def cmd_ai_summary(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 4):
        return
    import core_ai as ai
    cid = message.chat.id
    if not ai.available():
        return await message.reply("⚠️ Ключ ИИ не задан.")
    m = await message.reply("🧠 Читаю переписку…")
    ctx = await modlog.build_context(cid, 0)
    res = await ai.chat_summary(ctx)
    if not res:
        return await m.edit_text("😕 ИИ не ответил. Попробуйте позже.")
    mood = str(res.get("mood", "—"))
    out = [f"{ai.MOOD_ICON.get(mood, '💬')} <b>Обстановка: {mood}</b>\n",
           html.escape(str(res.get("summary", ""))[:600])]
    if res.get("problems"):
        out.append(f"\n⚠️ <b>Проблемы:</b>\n{html.escape(str(res['problems'])[:400])}")
    if res.get("advice"):
        out.append(f"\n💡 <b>Совет:</b>\n{html.escape(str(res['advice'])[:400])}")
    return await m.edit_text("\n".join(out))


@router.message(Cmd("ии проверь", "ии тест", section=S, rank=2,
                    usage="ии проверь [текст]", desc="🔍 Разовая проверка фразы через ИИ"))
async def cmd_ai_check(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    import core_ai as ai
    cid = message.chat.id
    probe = (args or "").strip()
    if not probe:
        return await message.reply("Формат: <code>ии проверь ты дебил</code>")
    if not ai.available():
        return await message.reply("⚠️ Ключ ИИ не задан.")
    m = await message.reply("🧠 Думаю…")
    ctx = await modlog.build_context(cid, 0)
    res = await ai.watch_message(probe, ctx)
    if not res:
        return await m.edit_text("😕 ИИ не ответил.")
    names = {0: "✅ норма", 1: "🟡 грубость",
             2: "🟠 оскорбление", 3: "🔴 мат/травля"}
    extra = (f"\n👤 Зачинщик: {html.escape(res['instigator'])}"
             if res.get("instigator") else "")
    category = (f"\n📌 Правило: {html.escape(res['category'])}"
                if res.get("category") else "")
    return await m.edit_text(
        f"🧠 <b>Оценка ИИ по правилам чата</b>\n\n"
        f"«{html.escape(probe[:150])}»\n\n"
        f"Вердикт: <b>{names[res['level']]}</b>{category}\n"
        f"💬 {html.escape(res['reason'])}{extra}")

    # статус
    alerts = await db.get_setting(cid, "ai_alerts", "1") == "1"
    watch = await db.get_setting(cid, "automod_ai", "1") == "1"
    stat = await db.fetchone(
        "SELECT COUNT(*) c FROM mod_log WHERE chat_id=? AND ai_verdict IS NOT NULL",
        (cid,))
    bad = await db.fetchone(
        "SELECT COUNT(*) c FROM mod_log WHERE chat_id=? AND ai_verdict "
        "IN ('harsh','wrong') AND ai_score>=6", (cid,))

    if not ai.available():
        return await message.reply(
            "🧠 <b>ИИ-надзор</b>\n\n"
            "Состояние: <b>🔴 ключ не задан</b>\n\n"
            "<b>Что даёт ИИ:</b>\n"
            "• проверяет каждое наказание — справедливо ли\n"
            "• пишет вам, если модератор перегнул\n"
            "• понимает контекст: отличает дружеский подкол\n"
            "  от настоящего оскорбления\n"
            "• делает сводку обстановки в чате\n\n"
            "<b>Как включить:</b>\n"
            "1. Возьмите ключ API (OpenAI, DeepSeek, OpenRouter)\n"
            "2. На хостинге добавьте переменную:\n"
            "   <code>AI_API_KEY</code> = ваш ключ\n"
            "3. Если сервис не OpenAI, добавьте ещё:\n"
            "   <code>AI_API_URL</code> и <code>AI_MODEL</code>\n"
            "4. Перезапустите бота\n\n"
            "<i>DeepSeek дешевле всего — около 1₽ за 1000 проверок.</i>")

    await message.reply(
        f"🧠 <b>ИИ-надзор</b>\n\n"
        f"Состояние: <b>🟢 работает</b>\n"
        f"Сервис: <b>{ai.provider()}</b>\n"
        f"Модель: <code>{html.escape(ai.MODEL)}</code>\n\n"
        f"👁 Следит за чатом: <b>{'да' if watch else 'нет'}</b>\n"
        f"🔔 Пишет о спорных наказаниях: <b>{'да' if alerts else 'нет'}</b>\n\n"
        f"📊 Проверено наказаний: <b>{stat['c']}</b>\n"
        f"⚠️ Спорных: <b>{bad['c']}</b>\n\n"
        f"<code>ии сводка</code> — что происходит в чате\n"
        f"<code>ии проверь текст</code> — оценить фразу\n"
        f"<code>ии оповещения выкл</code> — не писать в ЛС\n"
        f"<code>автомут ии выкл</code> — только словарь")


# ═══════════════ ВОПРОС К ИИ ═══════════════
@router.message(Cmd("спроси", "ask", "вопрос", "gpt", section=S, rank=0,
                    usage="спроси [вопрос]", desc="🧠 Задать вопрос искусственному интеллекту"))
async def cmd_ask_ai(message: Message, bot: Bot, args: str = "", **kw):
    """Ответ на вопрос участника чата через Google Gemini."""
    q = (args or "").strip()
    if not q:
        return await message.reply(
            "🧠 <b>Спросить ИИ</b>\n\n"
            "Использование: <code>спроси [ваш вопрос]</code>\n"
            "Пример: <code>спроси как играть в шахматы</code>")

    import core_ai as ai
    if not ai.available():
        return await message.reply("⚠️ ИИ временно недоступен.")

    m = await message.reply("🧠 Думаю над ответом…")
    ans = await ai.ask_text(
        q,
        system="Ты дружелюбный, лаконичный и полезный ИИ-помощник в русскоязычном игровом чате."
    )
    if not ans:
        return await m.edit_text("😕 Не удалось получить ответ от ИИ.")

    if len(ans) > 3900:
        ans = ans[:3900] + "\n\n<i>(ответ сокращён)</i>"
    await m.edit_text(f"🧠 <b>Ответ ИИ:</b>\n\n{html.escape(ans)}")


# ═══════════════ ФИЛЬТР ЗАПРЕЩЁННЫХ СЛОВ ═══════════════

@router.message(Cmd("+фильтр", "фильтр +", "фильтр добавить", section=S, rank=2,
                    usage="+фильтр [слово]", desc="Добавить слово в чёрный список чата"))
async def cmd_add_filter(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    word = (args or "").strip().lower()
    if not word or len(word) < 2:
        return await message.reply("Укажите запрещённое слово или фразу:\nПример: <code>+фильтр спам</code>")
    if len(word) > 50:
        return await message.reply("Слово слишком длинное (максимум 50 символов).")

    action = await db.get_setting(message.chat.id, "filter_action", "warn")
    await db.add_filtered_word(message.chat.id, word, action)
    act_str = "предупреждение (варн)" if action == "warn" else ("мут 1 час" if action == "mute" else "тихое удаление")
    await message.reply(
        f"✅ Слово «<b>{html.escape(word)}</b>» добавлено в чёрный список чата!\n"
        f"⚡️ Действие при нарушении: <b>{act_str}</b>."
    )


@router.message(Cmd("-фильтр", section=S, rank=2,
                    usage="-фильтр [слово]", desc="Удалить слово из чёрного списка чата"))
async def cmd_remove_filter(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 2):
        return
    word = (args or "").strip().lower()
    if not word:
        return await message.reply("Укажите слово для удаления из фильтра:\nПример: <code>-фильтр спам</code>")
    await db.remove_filtered_word(message.chat.id, word)
    await message.reply(f"🗑 Слово «<b>{html.escape(word)}</b>» удалено из чёрного списка чата.")


@router.message(Cmd("фильтры", "фильтр список", "черный список слов", "чс слов", section=S, rank=1,
                    usage="фильтры", desc="Список запрещённых слов в чате"))
async def cmd_list_filters(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 1):
        return
    words = await db.get_filtered_words(message.chat.id)
    if not words:
        return await message.reply(
            "📋 В чёрном списке чата пока нет добавленных слов.\n\n"
            "Добавить: <code>+фильтр [слово]</code>"
        )
    action = await db.get_setting(message.chat.id, "filter_action", "warn")
    act_str = "предупреждение (варн)" if action == "warn" else ("мут 1 час" if action == "mute" else "тихое удаление")
    lines = [
        f"📋 <b>ЧЁРНЫЙ СПИСОК СЛОВ ЧАТА ({len(words)}):</b>",
        f"⚙️ <i>Текущее действие: <b>{act_str}</b></i>\n"
    ]
    for idx, w in enumerate(words, 1):
        lines.append(f"{idx}. <code>{html.escape(w['word'])}</code>")
    lines.append("\n💡 <i>Добавить: <code>+фильтр [слово]</code> · Удалить: <code>-фильтр [слово]</code></i>")
    await message.reply("\n".join(lines))


@router.message(Cmd("фильтр режим", "фильтр действие", section=S, rank=4,
                    usage="фильтр режим варн|мут|удаление", desc="Настроить действие фильтра слов"))
async def cmd_filter_action(message: Message, bot: Bot, args: str = "", **kw):
    if not await require(message, bot, 4):
        return
    a = (args or "").strip().lower()
    if a in {"мут", "mute"}:
        await db.set_setting(message.chat.id, "filter_action", "mute")
        return await message.reply("🔇 Теперь за запрещённые слова выдаётся <b>мут на 1 час</b>.")
    if a in {"варн", "warn", "предупреждение"}:
        await db.set_setting(message.chat.id, "filter_action", "warn")
        return await message.reply("⚠️ Теперь за запрещённые слова выдаётся <b>предупреждение (варн)</b>.")
    if a in {"удаление", "удалять", "delete"}:
        await db.set_setting(message.chat.id, "filter_action", "delete")
        return await message.reply("🗑 Теперь запрещённые сообщения просто <b>удаляются</b> без наказания.")
    cur = await db.get_setting(message.chat.id, "filter_action", "warn")
    await message.reply(
        f"⚙️ Текущий режим фильтра: <b>{cur}</b>\n\n"
        f"Изменить: <code>фильтр режим мут</code> / <code>фильтр режим варн</code> / <code>фильтр режим удаление</code>"
    )


@router.message(Cmd("фильтр очистить", "фильтр сброс", section=S, rank=5,
                    usage="фильтр очистить", desc="Очистить все запрещённые слова в чате"))
async def cmd_clear_filters(message: Message, bot: Bot, **kw):
    if not await require(message, bot, 5):
        return
    await db.clear_filtered_words(message.chat.id)
    await message.reply("🧹 Чёрный список слов чата полностью очищен.")
