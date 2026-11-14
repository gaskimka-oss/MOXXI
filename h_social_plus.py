"""Модуль расширенной социалки, клановых войн и интерактива:
31. Войны за районы города для кланов
33. Клановые щиты и прокачка комнат штаба
34. Клановые альянсы и пакты
35. Клановые еженедельные контракты
36. Личный статус/био в карточке профиля
37. Стена профиля / Памятные росписи
39. Наставничество (Учитель и ученик с +5% бонусом)
40. Витрина достижений и медалей
41. Комплименты и рейтинг симпатий
47. Дни рождения участников чата
48. Аналитика активности чата
50. Промокоды на монеты
"""
from __future__ import annotations

import html
import random
import time
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import human_period, resolve_target
from utils import mention_id

router = Router(name="social_plus")

# 5 Районов города для захвата кланами
DISTRICTS = {
    "center": {"name": "🏛 Деловой Центр", "income": 5000, "desc": "Финансовый центр: приносит +5,000 монет в день в казну."},
    "port": {"name": "⚓️ Морской Порт", "income": 3500, "desc": "Контрабанда и грузы: приносит +3,500 монет в день."},
    "prom": {"name": "🏭 Промзона", "income": 2500, "desc": "Заводы и фабрики: приносит +2,500 монет в день."},
    "rublevka": {"name": "🏰 Золотая Рублёвка", "income": 6000, "desc": "Элитные виллы: приносит +6,000 монет в день."},
    "bazaar": {"name": "🏮 Центральный Базар", "income": 2000, "desc": "Торговые ряды: приносит +2,000 монет в день."},
}


# ---------------- 31. РАЙОНЫ И ЗАХВАТ ДЛЯ КЛАНОВ ----------------
@router.message(Cmd("районы", "карта города", usage="районы",
                    desc="🗺 Районы города и контроль кланами"))
async def cmd_districts(message: Message, bot: Bot, **kw):
    rows = await db.fetchall("SELECT * FROM clan_districts")
    controlled = {r["district_id"]: r["clan_id"] for r in rows}

    lines = ["🗺 <b>КАРТА РАЙОНОВ ГОРОДА</b>\n"]
    for d_id, d in DISTRICTS.items():
        cid = controlled.get(d_id)
        if cid:
            clan_row = await db.fetchone("SELECT name FROM clans WHERE id=?", (cid,))
            c_name = clan_row["name"] if clan_row else f"Клан #{cid}"
            status = f"🚩 Захвачен: <b>{html.escape(c_name)}</b>"
        else:
            status = "⚪️ <i>Свободен для захвата</i>"

        lines.append(
            f"<b>{d['name']}</b>\n"
            f"• Доход: <b>+{d['income']:,} монет/день</b> в казну\n"
            f"• Статус: {status}\n"
            f"• Захватить: <code>клан захват {d_id}</code>\n"
        )

    await message.reply("\n".join(lines))


@router.message(Cmd("клан захват", "захват района", usage="клан захват [код_района]",
                    desc="Начать захват района для своего клана"))
async def cmd_capture_district(message: Message, bot: Bot, args: str = "", **kw):
    d_id = (args or "").strip().lower()
    if not d_id or d_id not in DISTRICTS:
        return await message.reply("Укажите район: <code>клан захват center</code> (список: <code>районы</code>).")

    # Проверка клана
    c_mem = await db.fetchone("SELECT clan_id FROM clan_members WHERE user_id=?", (message.from_user.id,))
    if not c_mem:
        return await message.reply("Вы не состоите ни в одном клане!")

    clan_id = c_mem["clan_id"]
    clan_row = await db.fetchone("SELECT name, owner_id FROM clans WHERE id=?", (clan_id,))
    if not clan_row:
        return await message.reply("Клан не найден.")

    cur_row = await db.fetchone("SELECT clan_id, captured_ts FROM clan_districts WHERE district_id=?", (d_id,))
    now = int(time.time())
    if cur_row and cur_row["clan_id"] == clan_id:
        return await message.reply("Ваш клан уже контролирует этот район!")

    # Кулдаун битвы за район — 4 часа
    if cur_row and now - cur_row["captured_ts"] < 14400:
        rem = 14400 - (now - cur_row["captured_ts"])
        return await message.reply(f"🛡 Этот район недавно отбивался! До следующей осады: <b>{human_period(rem)}</b>.")

    await db.execute(
        "INSERT INTO clan_districts (district_id, clan_id, captured_ts) VALUES (?, ?, ?) "
        "ON CONFLICT(district_id) DO UPDATE SET clan_id=excluded.clan_id, captured_ts=excluded.captured_ts",
        (d_id, clan_id, now)
    )

    d_info = DISTRICTS[d_id]
    await message.reply(
        f"🚩 💥 <b>РАЙОН ЗАХВАЧЕН КЛАНОМ {html.escape(clan_row['name'])}!</b> 💥 🚩\n\n"
        f"🏰 Новый владелец района <b>{d_info['name']}</b>: клан <b>{html.escape(clan_row['name'])}</b>!\n"
        f"💰 Казна клана будет ежедневно получать <b>+{d_info['income']:,} монет</b> пассивной дани!"
    )


# ---------------- 34. КЛАНОВЫЕ АЛЬЯНСЫ ----------------
@router.message(Cmd("клан союз", "союз кланов", usage="клан союз [название]",
                    desc="🤝 Заключить пакт о ненападении с другим кланом"))
async def cmd_clan_alliance(message: Message, bot: Bot, args: str = "", **kw):
    c_mem = await db.fetchone("SELECT clan_id FROM clan_members WHERE user_id=?", (message.from_user.id,))
    if not c_mem:
        return await message.reply("Вы не состоите в клане!")
    my_clan = await db.fetchone("SELECT id, name, owner_id FROM clans WHERE id=?", (c_mem["clan_id"],))
    if my_clan["owner_id"] != message.from_user.id:
        return await message.reply("Заключать союзы может только Лидер клана.")

    target_name = (args or "").strip()
    if not target_name:
        return await message.reply("Укажите имя клана-союзника: <code>клан союз Легенды</code>")

    tgt_clan = await db.fetchone("SELECT id, name FROM clans WHERE lower(name)=lower(?)", (target_name,))
    if not tgt_clan:
        return await message.reply("Такой клан не найден.")
    if tgt_clan["id"] == my_clan["id"]:
        return await message.reply("Нельзя заключить союз с самим собой.")

    c1, c2 = min(my_clan["id"], tgt_clan["id"]), max(my_clan["id"], tgt_clan["id"])
    now = int(time.time())
    await db.execute(
        "INSERT OR REPLACE INTO clan_alliances (clan1_id, clan2_id, ts) VALUES (?, ?, ?)",
        (c1, c2, now)
    )
    await message.reply(
        f"🤝 <b>ВОЕННЫЙ АЛЬЯНС ЗАКЛЮЧЕН!</b>\n\n"
        f"Клан <b>{html.escape(my_clan['name'])}</b> и клан <b>{html.escape(tgt_clan['name'])}</b> "
        f"подписали пакт о ненападении и взаимопомощи! 🛡"
    )


# ---------------- 36. ЛИЧНЫЙ СТАТУС / БИО В ПРОФИЛЕ ----------------
@router.message(Cmd("+статус", "+био", "установить статус", usage="+статус [текст]",
                    desc="✏️ Установить личную цитату/статус в карточке профиля"))
async def cmd_set_status(message: Message, bot: Bot, args: str = "", **kw):
    txt = (args or "").strip()
    if not txt:
        return await message.reply("Введите ваш статус: <code>+статус Живу кайфую 🦁</code>")
    if len(txt) > 80:
        return await message.reply("Статус не должен превышать 80 символов.")

    now = int(time.time())
    await db.execute(
        "INSERT INTO user_bios (user_id, bio, updated_ts) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET bio=excluded.bio, updated_ts=excluded.updated_ts",
        (message.from_user.id, txt, now)
    )
    await message.reply(f"✅ <b>Статус обновлен:</b>\n«<i>{html.escape(txt)}</i>»\n(Он отобразится в вашем профиле).")


@router.message(Cmd("-статус", "-био", "удалить статус", usage="-статус",
                    desc="Удалить статус из профиля"))
async def cmd_del_status(message: Message, bot: Bot, **kw):
    await db.execute("DELETE FROM user_bios WHERE user_id=?", (message.from_user.id,))
    await message.reply("🗑 Ваш личный статус успешно удалён.")


# ---------------- 37. СТЕНА ПРОФИЛЯ / РОСПИСИ ----------------
@router.message(Cmd("роспись", "+роспись", usage="роспись {ссылка} [пожелание]",
                    desc="✍️ Оставить памятную роспись на стене пользователя"))
async def cmd_sign_wall(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите пользователя: реплаем или @ником.")
    if uid == message.from_user.id:
        return await message.reply("Нельзя расписываться на собственной стене!")

    txt = (rest or "❤️ Отличный бро!").strip()
    if len(txt) > 100:
        return await message.reply("Текст росписи не должен превышать 100 символов.")

    sender_name = message.from_user.first_name or "Друг"
    now = int(time.time())
    await db.execute(
        "INSERT INTO profile_wall (target_id, author_id, author_name, text, ts) VALUES (?, ?, ?, ?, ?)",
        (uid, message.from_user.id, sender_name, txt, now)
    )
    await message.reply(
        f"✍️ <b>РОСПИСЬ ОСТАВЛЕНА!</b>\n\n"
        f"👤 На стене у {mention_id(uid, name)}\n"
        f"📝 <i>«{html.escape(txt)}»</i>\n"
        f"Посмотреть стену: <code>стена {mention_id(uid, name)}</code>"
    )


@router.message(Cmd("стена", "росписи", usage="стена {ссылка}",
                    desc="Посмотреть росписи на стене игрока"))
async def cmd_view_wall(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    uid = uid or message.from_user.id
    name = name or message.from_user.first_name

    rows = await db.fetchall(
        "SELECT * FROM profile_wall WHERE target_id=? ORDER BY id DESC LIMIT 10",
        (uid,)
    )
    if not rows:
        return await message.reply(f"📝 На стене у {mention_id(uid, name)} пока нет росписей. Будьте первыми: <code>роспись {mention_id(uid, name)} [текст]</code>")

    lines = [f"✍️ <b>СТЕНА РОСПИСЕЙ {mention_id(uid, name)}:</b>\n"]
    for idx, r in enumerate(rows, 1):
        dt = time.strftime("%d.%m.%Y", time.localtime(r["ts"]))
        lines.append(f"<b>{idx}.</b> <b>{html.escape(r['author_name'])}</b> (<i>{dt}</i>):\n   «{html.escape(r['text'])}»\n")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


# ---------------- 39. НАСТАВНИЧЕСТВО (УЧИТЕЛЬ И УЧЕНИК) ----------------
@router.message(Cmd("учитель", "стать учителем", usage="учитель {ссылка}",
                    desc="👨‍🏫 Взять игрока в ученики (бонус +5% обоим)"))
async def cmd_become_mentor(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите ученика: реплаем или @ником.")
    if uid == message.from_user.id:
        return await message.reply("Нельзя быть учителем самому себе!")

    # Проверка, есть ли уже учитель у цели
    cur_m = await db.fetchone("SELECT teacher_id FROM mentorships WHERE student_id=?", (uid,))
    if cur_m:
        return await message.reply("У этого игрока уже есть наставник!")

    await db.execute(
        "INSERT INTO mentorships (teacher_id, student_id, ts) VALUES (?, ?, ?)",
        (message.from_user.id, uid, int(time.time()))
    )
    await message.reply(
        f"👨‍🏫 <b>СОЮЗ НАСТАВНИЧЕСТВА ЗАКЛЮЧЁН!</b>\n\n"
        f"🎓 Учитель: {mention_id(message.from_user.id, message.from_user.first_name)}\n"
        f"🎒 Ученик: {mention_id(uid, name)}\n\n"
        f"✨ Оба получают <b>+5% бонус</b> к опыту и доходу с работы!"
    )


# ---------------- 41. СИМПАТИИ И КОМПЛИМЕНТЫ ----------------
@router.message(Cmd("комплимент", "симпатия", "+симпатия", usage="комплимент {ссылка}",
                    desc="❤️ Сделать комплимент и повысить обаяние участника"))
async def cmd_give_compliment(message: Message, bot: Bot, args: str = "", **kw):
    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        return await message.reply("Укажите участника: реплаем или @ником.")
    if uid == message.from_user.id:
        return await message.reply("Себе комплименты делать приятно, но очки обаяния не начисляются! 😉")

    now = int(time.time())
    await db.execute(
        "INSERT INTO user_compliments (user_id, count, last_given) VALUES (?, 1, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET count=count+1, last_given=?",
        (uid, now, now)
    )
    c_row = await db.fetchone("SELECT count FROM user_compliments WHERE user_id=?", (uid,))
    tot = c_row["count"] if c_row else 1

    compliments = [
        "Твоя улыбка освещает весь этот чат! ✨",
        "С тобой общение всегда на высоте! 🌟",
        "Самый душевный и приятный человечек беседы! 💖",
        "Твоей харизме можно только позавидовать! 🔥"
    ]
    txt = random.choice(compliments)

    await message.reply(
        f"❤️ <b>КОМПЛИМЕНТ ДЛЯ {mention_id(uid, name)}!</b>\n\n"
        f"💌 <i>«{txt}»</i>\n\n"
        f"🌹 Обаяние: <b>{tot} сердечек</b> от участников чата!"
    )


# ---------------- 47. ДНИ РОЖДЕНИЯ ЧАТА ----------------
@router.message(Cmd("+др", "мой др", "день рождения", usage="+др [ДД.ММ]",
                    desc="🎂 Записать свой день рождения для поздравлений"))
async def cmd_set_birthday(message: Message, bot: Bot, args: str = "", **kw):
    a = (args or "").strip()
    parts = a.split(".")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return await message.reply("Укажите день и месяц через точку, например: <code>+др 15.08</code> или <code>+др 03.11</code>")

    day, month = int(parts[0]), int(parts[1])
    if day < 1 or day > 31 or month < 1 or month > 12:
        return await message.reply("Укажите корректную дату.")

    await db.execute(
        "INSERT INTO chat_birthdays (chat_id, user_id, day, month) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET day=excluded.day, month=excluded.month",
        (message.chat.id, message.from_user.id, day, month)
    )
    await message.reply(f"🎂 <b>Дата дня рождения сохранена: {day:02d}.{month:02d}!</b> В этот день чат обязательно вас поздравит!")


@router.message(Cmd("др список", "именинники", usage="др список",
                    desc="Показать дни рождения участников чата"))
async def cmd_list_birthdays(message: Message, bot: Bot, **kw):
    rows = await db.fetchall("SELECT * FROM chat_birthdays WHERE chat_id=? ORDER BY month, day LIMIT 30", (message.chat.id,))
    if not rows:
        return await message.reply("В этом чате пока никто не записал свой день рождения (команда: <code>+др ДД.ММ</code>).")

    lines = ["🎂 <b>КАЛЕНДАРЬ ДНЕЙ РОЖДЕНИЙ ЧАТА:</b>\n"]
    for r in rows:
        u = await db.get_user(r["user_id"])
        u_name = u["first_name"] if u else f"ID {r['user_id']}"
        lines.append(f"• <b>{r['day']:02d}.{r['month']:02d}</b> — {mention_id(r['user_id'], u_name)}")

    await message.reply("\n".join(lines))


# ---------------- 50. СЕКРЕТНЫЕ ПРОМОКОДЫ (ТОЛЬКО ВЛАДЕЛЬЦЫ БОТА) ----------------
@router.message(Cmd("+промо", "+промовип", "+промовип+", "+промовип++", "создать промо", "создать промокод",
                    rank=0, group_only=False,
                    usage="+промо [код] [кол-во] [награда / вип / вип++ [дней]]",
                    desc="🎁 Создать промокод на монеты, VIP или VIP++ (ТОЛЬКО Создатели бота)"))
async def cmd_create_promocode(message: Message, bot: Bot, args: str = "", **kw):
    import config
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Создавать промокоды могут <b>ТОЛЬКО Создатели бота</b>!\n\nОстальным пользователям и администраторам групп создание промокодов строго запрещено.")

    raw_text = (message.text or "").strip()
    cmd_name = raw_text.split()[0].lower() if raw_text else ""
    tokens = (args or "").strip().split()

    reward_type = "coins"
    code = ""
    uses = 0
    reward = 0
    duration_days = 0

    if "вип++" in cmd_name or "vipplus" in cmd_name or "vip++" in cmd_name:
        reward_type = "vipplus"
    elif "вип+" in cmd_name or "vip+" in cmd_name:
        reward_type = "vipplus"
    elif "вип" in cmd_name or "vip" in cmd_name:
        reward_type = "vip"

    if not tokens:
        return await message.reply(
            "🎁 <b>Форматы создания промокодов (для Создателей):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 <b>На VIP++ (VIP+ Diamond):</b>\n"
            "• <code>+промо вип++ [КОД] [АКТИВАЦИЙ] [ДНЕЙ]</code>\n"
            "👉 <i>Пример:</i> <code>+промо вип++ СУПЕР9 20 9</code>\n\n"
            "⭐️ <b>На VIP (обычный):</b>\n"
            "• <code>+промо вип [КОД] [АКТИВАЦИЙ] [ДНЕЙ]</code>\n"
            "👉 <i>Пример:</i> <code>+промо вип ЛЕТО 20 9</code>\n\n"
            "💰 <b>На монеты:</b>\n"
            "• <code>+промо [КОД] [АКТИВАЦИЙ] [СУММА]</code>\n"
            "👉 <i>Пример:</i> <code>+промо ВЕСНА 20 5000</code>"
        )

    # 1. Формат: +промо вип++ [код] [кол-во] [дней]
    p0 = tokens[0].lower()
    if p0 in ("вип", "vip", "вип+", "vip+", "вип++", "vip++", "vipplus"):
        reward_type = "vipplus" if ("+" in p0 or "plus" in p0) else "vip"
        if len(tokens) >= 4 and tokens[2].isdigit() and tokens[3].isdigit():
            code = tokens[1].upper()
            uses = int(tokens[2])
            duration_days = int(tokens[3])
        elif len(tokens) == 3 and tokens[1].isdigit() and tokens[2].isdigit():
            code = f"{'VIPPLUS' if reward_type == 'vipplus' else 'VIP'}{int(time.time()) % 10000}"
            uses = int(tokens[1])
            duration_days = int(tokens[2])
        else:
            return await message.reply("⚠️ Формат: <code>+промо вип++ КОД 20 9</code> (Код, активаций, дней)")

    # 2. Если команда была "+промовип++" или "+промовип"
    elif reward_type in ("vip", "vipplus"):
        if len(tokens) >= 3 and tokens[1].isdigit() and tokens[2].isdigit():
            code = tokens[0].upper()
            uses = int(tokens[1])
            duration_days = int(tokens[2])
        else:
            return await message.reply(f"⚠️ Формат: <code>+{cmd_name} КОД 20 9</code>")

    # 3. Универсальный формат: +промо [код] [кол-во] вип++ [дней]
    elif len(tokens) >= 4 and tokens[1].isdigit() and tokens[2].lower() in ("вип", "vip", "вип+", "vip+", "вип++", "vip++", "vipplus") and tokens[3].isdigit():
        p2 = tokens[2].lower()
        reward_type = "vipplus" if ("+" in p2 or "plus" in p2) else "vip"
        code = tokens[0].upper()
        uses = int(tokens[1])
        duration_days = int(tokens[3])

    # 4. Стандартный промокод на монеты: +промо [код] [кол-во] [награда]
    elif len(tokens) >= 3 and tokens[1].isdigit() and tokens[2].isdigit():
        code = tokens[0].upper()
        uses = int(tokens[1])
        reward = int(tokens[2])
        reward_type = "coins"

    else:
        return await message.reply(
            "⚠️ <b>Неверный формат команды!</b>\n"
            "• На VIP++: <code>+промо вип++ КОД 20 9</code>\n"
            "• На VIP: <code>+промо вип КОД 20 9</code>\n"
            "• На монеты: <code>+промо КОД 20 5000</code>"
        )

    if uses <= 0:
        return await message.reply("❌ Число активаций должно быть больше 0!")

    now = int(time.time())

    await db.execute(
        "INSERT INTO promocodes (code, chat_id, reward, uses_left, created_by, ts, reward_type, duration_days) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(code) DO UPDATE SET uses_left=excluded.uses_left, reward=excluded.reward, reward_type=excluded.reward_type, duration_days=excluded.duration_days",
        (code, message.chat.id, reward, uses, message.from_user.id, now, reward_type, duration_days)
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Разослать промокод во все группы", callback_data=f"promo_bc:{code}")]
    ])

    if reward_type == "vipplus":
        reward_desc = f"🌟 <b>VIP+ Diamond (VIP++) на {duration_days} дней</b>"
    elif reward_type == "vip":
        reward_desc = f"⭐️ <b>VIP на {duration_days} дней</b>"
    else:
        reward_desc = f"💰 <b>+{reward:,} монет</b>"

    await message.reply(
        f"🎁 <b>ПРОМОКОД УСПЕШНО СОЗДАН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Код: <code>{code}</code>\n"
        f"👥 Активаций: <b>{uses} шт.</b>\n"
        f"🎁 Награда: {reward_desc} каждому!\n\n"
        f"👉 <b>Активация для игроков:</b> <code>промо {code}</code>\n\n"
        f"💡 <i>Нажмите кнопку ниже или введите <code>разослать промо {code}</code>, чтобы отправить промокод во все чаты (TG • VK • DS • MAX)!</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("promo_bc:"))
async def cb_broadcast_promocode(cq: CallbackQuery, bot: Bot):
    import config
    sender_id = cq.from_user.id if cq.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await cq.answer("⛔️ Рассылать промокод могут только Создатели бота!", show_alert=True)

    code = cq.data.split(":", 1)[1].strip().upper()
    row = await db.fetchone("SELECT * FROM promocodes WHERE code=?", (code,))
    if not row or row["uses_left"] <= 0:
        return await cq.answer("⚠️ Промокод не существует или закончился!", show_alert=True)

    await cq.answer("📢 Запуск мульти-рассылки во все платформы (TG • VK • DS • MAX)...")

    reward_type = (row["reward_type"] or "coins").lower() if "reward_type" in row.keys() else "coins"
    duration_days = row["duration_days"] if "duration_days" in row.keys() and row["duration_days"] else 0

    from core_cross_broadcast import cross_broadcast_promo
    stats = await cross_broadcast_promo(bot, code, row["reward"], row["uses_left"], reward_type=reward_type, duration_days=duration_days)

    if reward_type == "vipplus":
        rew_info = f"🌟 <b>VIP++ на {duration_days} дней</b>"
    elif reward_type == "vip":
        rew_info = f"⭐️ <b>VIP на {duration_days} дней</b>"
    else:
        rew_info = f"💰 <b>+{row['reward']:,} монет</b>"

    try:
        await cq.message.reply(
            f"✅ <b>МУЛЬТИПЛАТФОРМЕННАЯ РАССЫЛКА ПРОМОКОДА ЗАВЕРШЕНА!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 Промокод: <code>{code}</code>\n"
            f"🎁 Награда: {rew_info} каждому!\n"
            f"👥 Всего активаций: <b>{row['uses_left']} шт.</b>\n\n"
            f"📊 <b>СТАТИСТИКА ДОСТАВКИ ПО ПЛАТФОРМАМ:</b>\n"
            f"• ✈️ Telegram: <b>{stats.get('telegram', 0)} групп</b>\n"
            f"• 🟦 ВКонтакте: <b>{stats.get('vk', 0)} бесед</b>\n"
            f"• 🟣 Discord: <b>{stats.get('discord', 0)} серверов</b>\n"
            f"• 🟢 MAX: <b>{stats.get('max', 0)} чатов</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 <i>Промокод синхронизирован и активен на всех 4 платформах!</i>"
        )
    except Exception:
        pass


@router.message(Cmd("разослать промо", "рассылка промо", "промо рассылка", "разослать промокод", rank=0, group_only=False,
                    usage="разослать промо [код]", desc="📢 Разослать промокод во все группы бота (ТОЛЬКО Создатели)"))
async def cmd_broadcast_promocode(message: Message, bot: Bot, args: str = "", **kw):
    import config
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Рассылать промокоды могут <b>ТОЛЬКО Создатели бота</b>!")

    code = (args or "").strip().upper()
    if not code:
        row = await db.fetchone("SELECT * FROM promocodes WHERE uses_left > 0 ORDER BY ts DESC LIMIT 1")
        if not row:
            return await message.reply("⚠️ Укажите промокод: <code>разослать промо ОБНОВА3.0</code>")
        code = row["code"]
    else:
        row = await db.fetchone("SELECT * FROM promocodes WHERE code=?", (code,))

    if not row or row["uses_left"] <= 0:
        return await message.reply("⚠️ Промокод не найден или у него закончились активации!")

    reward_type = (row["reward_type"] or "coins").lower() if "reward_type" in row.keys() else "coins"
    duration_days = row["duration_days"] if "duration_days" in row.keys() and row["duration_days"] else 0

    m = await message.reply(
        f"📢 <b>Начинаю мультиплатформенную рассылку промокода <code>{code}</code>…</b>\n"
        f"📡 Платформы: ✈️ Telegram • 🟦 VK • 🟣 Discord • 🟢 MAX\n"
        f"Пожалуйста, подождите завершения отправки."
    )

    from core_cross_broadcast import cross_broadcast_promo
    stats = await cross_broadcast_promo(bot, code, row["reward"], row["uses_left"], reward_type=reward_type, duration_days=duration_days)

    if reward_type == "vipplus":
        rew_info = f"🌟 <b>VIP++ на {duration_days} дней</b>"
    elif reward_type == "vip":
        rew_info = f"⭐️ <b>VIP на {duration_days} дней</b>"
    else:
        rew_info = f"💰 <b>+{row['reward']:,} монет</b>"

    await m.edit_text(
        f"✅ <b>МУЛЬТИПЛАТФОРМЕННАЯ РАССЫЛКА ПРОМОКОДА ЗАВЕРШЕНА!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Промокод: <code>{code}</code>\n"
        f"🎁 Награда: {rew_info} каждому!\n"
        f"👥 Всего активаций: <b>{row['uses_left']} шт.</b>\n\n"
        f"📊 <b>СТАТИСТИКА ДОСТАВКИ ПО ПЛАТФОРМАМ:</b>\n"
        f"• ✈️ Telegram: <b>{stats.get('telegram', 0)} групп</b>\n"
        f"• 🟦 ВКонтакте: <b>{stats.get('vk', 0)} бесед</b>\n"
        f"• 🟣 Discord: <b>{stats.get('discord', 0)} серверов</b>\n"
        f"• 🟢 MAX: <b>{stats.get('max', 0)} чатов</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <i>Промокод успешно синхронизирован во все базы и открыт для игроков!</i>"
    )


@router.message(Cmd("промо", "промокод", usage="промо [код]",
                    desc="Активировать промокод и забрать монеты, VIP или VIP++"))
async def cmd_activate_promocode(message: Message, bot: Bot, args: str = "", **kw):
    code = (args or "").strip().upper()
    if not code:
        return await message.reply("Введите промокод: <code>промо ВЕСНА</code>")

    row = await db.fetchone("SELECT * FROM promocodes WHERE code=?", (code,))
    if not row or row["uses_left"] <= 0:
        return await message.reply("⚠️ Промокод не существует или закончился!")

    uid = message.from_user.id
    used = await db.fetchone("SELECT 1 FROM promocode_activations WHERE code=? AND user_id=?",
                             (code, uid))
    if used:
        return await message.reply("⛔️ Вы уже активировали этот промокод!")

    now = int(time.time())
    await db.execute("INSERT INTO promocode_activations (code, user_id, ts) VALUES (?, ?, ?)",
                     (code, uid, now))
    await db.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (code,))

    rem = row["uses_left"] - 1
    total_act = await db.fetchone("SELECT COUNT(*) as cnt FROM promocode_activations WHERE code=?", (code,))
    claimed_cnt = total_act["cnt"] if total_act else 1
    total_initial = claimed_cnt + rem

    reward_type = (row["reward_type"] or "coins").lower() if "reward_type" in row.keys() else "coins"
    duration_days = row["duration_days"] if "duration_days" in row.keys() and row["duration_days"] else 0

    if reward_type in ("vipplus", "vip++", "vip+"):
        target_lvl = 2
        status_name = "🌟 VIP+ Diamond (VIP++)"
        days = duration_days or 9
        cur_lvl, cur_until, is_active = await db.get_vip_info(uid)
        start_time = max(now, cur_until if (is_active and cur_lvl >= target_lvl) else now)
        new_until = start_time + days * 86400
        await db.set_vip(uid, new_until, level=target_lvl)
        import datetime
        exp_date = datetime.datetime.fromtimestamp(new_until).strftime("%d.%m.%Y в %H:%M")

        reward_text = (
            f"👑 <b>Привилегия выдана:</b> {status_name}\n"
            f"⏳ <b>Срок действия:</b> +{days} дней (активен до {exp_date})\n\n"
            f"💎 <b>Ваши новые возможности VIP++:</b>\n"
            f"• Доступ к персональному VIP-сейфу и овердрафту\n"
            f"• Удвоенные ежедневные бонусы и супердропы\n"
            f"• Эксклюзивные темы оформления («вип темы»)\n"
            f"• 21 уникальная суперсила и приоритет в поддержке!"
        )
    elif reward_type == "vip":
        target_lvl = 1
        status_name = "⭐️ VIP"
        days = duration_days or 7
        cur_lvl, cur_until, is_active = await db.get_vip_info(uid)
        start_time = max(now, cur_until if (is_active and cur_lvl >= target_lvl) else now)
        new_until = start_time + days * 86400
        await db.set_vip(uid, new_until, level=target_lvl)
        import datetime
        exp_date = datetime.datetime.fromtimestamp(new_until).strftime("%d.%m.%Y в %H:%M")

        reward_text = (
            f"⭐️ <b>Привилегия выдана:</b> {status_name}\n"
            f"⏳ <b>Срок действия:</b> +{days} дней (активен до {exp_date})\n\n"
            f"💎 <b>Ваши новые возможности VIP:</b>\n"
            f"• Персональные неоновые темы оформления («вип темы»)\n"
            f"• Повышенные бонусы и лимиты переводов\n"
            f"• Золотая звезда VIP в профиле!"
        )
    else:
        await db.add_coins(uid, row["reward"], "promocode_reward", code)
        reward_text = f"💰 Вам начислено: <b>+{row['reward']:,} монет</b> на баланс!"

    if rem > 0:
        await message.reply(
            f"🎉 <b>ПРОМОКОД УСПЕШНО АКТИВИРОВАН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{reward_text}\n\n"
            f"⚡ <b>Кто-то уже забрал!</b> (Забрали <b>{claimed_cnt} из {total_initial}</b> промов, осталось: <b>{rem} шт.</b>)"
        )
    else:
        await message.reply(
            f"🎉 <b>ПРОМОКОД УСПЕШНО АКТИВИРОВАН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{reward_text}\n\n"
            f"🔥 <b>Кто-то забрал последний промокод!</b> (Все <b>{total_initial} из {total_initial}</b> промов розданы, наград больше нет!)"
        )

    # Уведомление создателю промокода в ЛС
    try:
        import config
        creator_id = row.get("created_by") or config.OWNER_ID
        chat_title = message.chat.title or "Личные сообщения"
        if creator_id:
            if rem > 0:
                await bot.send_message(
                    creator_id,
                    f"🎟️ <b>Активация промокода <code>{code}</code>!</b>\n"
                    f"💬 Чат: «{chat_title}»\n"
                    f"💰 Награда: +{row['reward']:,} монет\n"
                    f"⏳ <b>Осталось: {rem} шт.</b>"
                )
            else:
                await bot.send_message(
                    creator_id,
                    f"🏁 <b>Промокод <code>{code}</code> полностью закончился!</b>\n"
                    f"Последний забрали в чате «{chat_title}».\n"
                    f"Все награды успешно розданы игрокам!"
                )
        if config.OWNER_ID and config.OWNER_ID != creator_id:
            if rem > 0:
                await bot.send_message(
                    config.OWNER_ID,
                    f"🎟️ <b>Активация промокода <code>{code}</code>!</b>\n"
                    f"💬 Чат: «{chat_title}»\n"
                    f"⏳ <b>Осталось: {rem} шт.</b>"
                )
            else:
                await bot.send_message(
                    config.OWNER_ID,
                    f"🏁 <b>Промокод <code>{code}</code> полностью закончился!</b>\n"
                    f"Последний забрали в чате «{chat_title}»."
                )
    except Exception:
        pass


@router.callback_query(F.data.startswith("promo_claim:"))
async def cb_claim_promocode(cq: CallbackQuery, bot: Bot):
    """Активация промокода в 1 клик по инлайн-кнопке под постом рассылки."""
    code = cq.data.split(":", 1)[1].strip().upper()
    uid = cq.from_user.id

    row = await db.fetchone("SELECT * FROM promocodes WHERE code=?", (code,))
    if not row or row["uses_left"] <= 0:
        return await cq.answer("⚠️ Все промокоды уже разобрали! Активаций больше нет.", show_alert=True)

    used = await db.fetchone("SELECT 1 FROM promocode_activations WHERE code=? AND user_id=?",
                             (code, uid))
    if used:
        return await cq.answer("⛔️ Вы уже активировали этот промокод ранее!", show_alert=True)

    now = int(time.time())
    await db.execute("INSERT INTO promocode_activations (code, user_id, ts) VALUES (?, ?, ?)",
                     (code, uid, now))
    await db.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (code,))
    await db.add_coins(uid, row["reward"], "promocode_reward", code)

    rem = row["uses_left"] - 1

    total_act = await db.fetchone("SELECT COUNT(*) as cnt FROM promocode_activations WHERE code=?", (code,))
    claimed_cnt = total_act["cnt"] if total_act else 1
    total_initial = claimed_cnt + rem

    await cq.answer(f"🎉 Вы успешно забрали +{row['reward']:,} монет!\nОсталось: {rem} из {total_initial} шт.", show_alert=True)

    # Сообщение в чат (без юзернейма, чисто анонимный азарт)
    chat_title = cq.message.chat.title if cq.message and cq.message.chat else "Группа"
    if rem > 0:
        if cq.message:
            await cq.message.reply(
                f"⚡ <b>Кто-то уже забрал промокод!</b>\n"
                f"Забрали <b>{claimed_cnt} из {total_initial}</b> промов (осталось всего: <b>{rem} шт.</b>)! Поторопитесь!"
            )
    else:
        if cq.message:
            await cq.message.reply(
                f"🔥 <b>Кто-то забрал последний промокод!</b>\n"
                f"Все <b>{total_initial} из {total_initial}</b> промокодов <code>{code}</code> разобраны, наград больше нет!"
            )

    # Личное уведомление создателю в ЛС
    try:
        import config
        creator_id = row.get("created_by") or config.OWNER_ID
        if creator_id:
            if rem > 0:
                await bot.send_message(
                    creator_id,
                    f"🎟️ <b>Активация промокода <code>{code}</code> (кнопкой в 1 клик)!</b>\n"
                    f"💬 Чат: «{chat_title}»\n"
                    f"💰 Награда: +{row['reward']:,} монет\n"
                    f"⏳ <b>Осталось: {rem} шт.</b>"
                )
            else:
                await bot.send_message(
                    creator_id,
                    f"🏁 <b>Промокод <code>{code}</code> полностью закончился!</b>\n"
                    f"Последний забрали по кнопке в чате «{chat_title}»."
                )
        if config.OWNER_ID and config.OWNER_ID != creator_id:
            if rem > 0:
                await bot.send_message(
                    config.OWNER_ID,
                    f"🎟️ <b>Активация промокода <code>{code}</code> (в 1 клик)!</b>\n"
                    f"💬 Чат: «{chat_title}»\n"
                    f"⏳ <b>Осталось: {rem} шт.</b>"
                )
    except Exception:
        pass


@router.message(Cmd("промо инфо", "инфо промо", "статус промо", "промо статус", rank=0, group_only=False,
                    usage="промо инфо [код]", desc="📊 Статистика промокода (сколько осталось и кто активировал)"))
async def cmd_promocode_info(message: Message, bot: Bot, args: str = "", **kw):
    import config
    sender_id = message.from_user.id if message.from_user else 0
    if not config.is_bot_owner(sender_id):
        return await message.reply("⛔️ Просматривать статус промокодов могут только Создатели бота!")

    code = (args or "").strip().upper()
    if not code:
        row = await db.fetchone("SELECT * FROM promocodes ORDER BY ts DESC LIMIT 1")
    else:
        row = await db.fetchone("SELECT * FROM promocodes WHERE code=?", (code,))

    if not row:
        return await message.reply("⚠️ Промокод не найден.")

    total_row = await db.fetchone("SELECT COUNT(*) as cnt FROM promocode_activations WHERE code=?", (row["code"],))
    activated_count = total_row["cnt"] if total_row else 0
    total_initial = activated_count + row["uses_left"]

    await message.reply(
        f"📊 <b>Статистика промокода <code>{row['code']}</code>:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Награда: <b>+{row['reward']:,} монет</b>\n"
        f"👥 Активировано: <b>{activated_count} из {total_initial}</b>\n"
        f"⚡ <b>Осталось активаций: {row['uses_left']} шт.</b>\n"
        f"📅 Создан: {time.strftime('%d.%m.%Y %H:%M', time.localtime(row['ts']))}\n"
        f"Статус: {'🟢 Активен' if row['uses_left'] > 0 else '🔴 Исчерпан'}"
    )
