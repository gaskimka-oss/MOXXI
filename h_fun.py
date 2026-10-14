"""Разделы 13–16: бонусы/монеты/VIP, развлечения, дуэли, кубы."""
from __future__ import annotations

import asyncio
import html
import random
import re
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
import core_members as members
from config import (CRIME_COOLDOWN, CRIME_FINE, CRIME_REWARD, CRIME_SUCCESS_CHANCE,
                    DAILY_BONUS, DAILY_COOLDOWN, MAX_BET, MIN_BET, TRANSFER_FEE,
                    WORK_COOLDOWN, WORK_REWARD)
from core_ranks import require
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from utils import hms, level_of, mention, mention_id, money, parse_amount, make_game_replay_kb
from h_grams import topic_ok
from core_game_lock import lock_game, unlock_game, is_in_game

router = Router(name="fun")
S_BONUS, S_FUN, S_DUEL, S_CUBE = 13, 14, 15, 16


# ---------- 13. Работа, крайм и ограбления ----------
@router.message(Cmd("работа", "работать", "пахать", "work", section=S_BONUS,
                    usage="работа", desc="Заработать средства на текущей должности"))
async def cmd_work(message: Message, bot: Bot, **kw):
    from h_economy_plus import cmd_work as real_cmd_work
    return await real_cmd_work(message, bot, **kw)


@router.message(Cmd("крайм", "преступление", "рискнуть", section=S_BONUS,
                    usage="крайм", desc="Рискованный заработок (только в теме Казино)"))
async def cmd_crime(message: Message, **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    left = await db.cooldown_left(uid, "crime", CRIME_COOLDOWN)
    if left:
        return await message.reply(f"🚔 Заляг на дно ещё <b>{hms(left)}</b>.")
    await db.set_cooldown(uid, "crime")
    if random.random() < CRIME_SUCCESS_CHANCE:
        amount = random.randint(*CRIME_REWARD)
        bal = await db.add_balance(uid, amount, "crime_ok")
        return await message.reply(f"🕵️ Успех! <b>+{money(amount)}</b>\nБаланс: {money(bal)}")
    u = await db.get_user(uid)
    fine = min(u["balance"], random.randint(*CRIME_FINE))
    bal = await db.add_balance(uid, -fine, "crime_fail")
    await message.reply(f"🚨 Провал! <b>−{money(fine)}</b>\nБаланс: {money(bal)}")


@router.message(Cmd("украсть", "ограбить", "вор", "кража", "rob", "steal", "грабеж", "грабёж",
                    section=S_BONUS, usage="украсть {ссылка} [сумма]",
                    desc="Попробовать украсть средства у игрока (только в теме Казино)"))
async def cmd_rob(message: Message, bot: Bot, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    robber_id = message.from_user.id
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        if had_prefix or not in_group:
            return await message.reply(
                "🦹‍♂️ <b>Ограбление игрока</b>\n\n"
                "Формат: <code>украсть @юзер [сумма]</code>\n"
                "Пример: <code>украсть @Dima 500</code>\n\n"
                "💡 <i>Если ограбление удастся — вы заберёте средства жертвы.\n"
                "Если провалится — вы заплатите штраф и компенсацию жертве!</i>")
        return

    if uid == robber_id:
        return await message.reply("Себя ограбить нельзя 🙂")

    # Кулдаун на ограбления
    vip_lvl, _, vip_active = await db.get_vip_info(robber_id)
    cd = 600 if (vip_active and vip_lvl >= 2) else (1200 if (vip_active and vip_lvl >= 1) else 1800)
    left = await db.cooldown_left(robber_id, "rob_cd", cd)
    if left:
        return await message.reply(f"🚨 Полиция ещё ищет вас! Залягте на дно: <b>{hms(left)}</b>.")

    u_robber = await db.get_user(robber_id)
    u_victim = await db.get_user(uid)

    # Проверка, спрятан ли мешок у жертвы
    hide_left = await db.cooldown_left(uid, "bag_hidden", 5 * 3600)
    if hide_left:
        return await message.reply(
            f"🛡 <b>Мешок надёжно спрятан!</b>\n\n"
            f"{mention_id(uid, name)} спрятал свой мешок!\n"
            f"Украсть ничего не получится ещё <b>{hms(hide_left)}</b> 🔒")

    if u_robber["balance"] < 50:
        return await message.reply(f"У вас слишком мало средств ({money(u_robber['balance'])}). Нужно минимум {money(50)} на случай штрафа.")

    if u_victim["balance"] < 50:
        return await message.reply(f"У {mention_id(uid, name)} в карманах пусто (меньше {money(50)}). Красть нечего!")

    # Расчёт суммы (гарантированно положительное число)
    max_steal = min(u_victim["balance"], 50000)
    raw_amount = parse_amount(rest, u_victim["balance"])
    if raw_amount and raw_amount > 0:
        amount = max(1, min(int(raw_amount), max_steal))
    else:
        # По умолчанию случайная часть (15-30% от баланса жертвы, не более 10000)
        pct = random.uniform(0.15, 0.30)
        amount = max(50, min(int(u_victim["balance"] * pct), 10000))

    amount = max(1, min(amount, u_victim["balance"]))

    # Шанс успеха: базовый 45%, +10% VIP, +20% VIP+
    chance = 0.45
    if vip_active:
        if vip_lvl >= 2:
            chance += 0.20
        elif vip_lvl >= 1:
            chance += 0.10

    # Жертва с VIP имеет защиту
    v_vip_lvl, _, v_vip_act = await db.get_vip_info(uid)
    if v_vip_act:
        chance -= 0.10

    chance = max(0.20, min(0.80, chance))
    await db.set_cooldown(robber_id, "rob_cd")

    if random.random() < chance:
        # Успех
        await db.add_balance(uid, -amount, "robbed_by", str(robber_id))
        new_bal = await db.add_balance(robber_id, amount, "rob_win", str(uid))
        await message.reply(
            f"🦹‍♂️ <b>Успешное ограбление!</b>\n\n"
            f"{mention(message.from_user)} ловко вытащил из мешка {mention_id(uid, name)} <b>+{money(amount)}</b>! 💰\n\n"
            f"🎲 Вероятность успеха была: <b>{int(chance * 100)}%</b>\n"
            f"🪙 Ваш новый баланс: <b>{money(new_bal)}</b>")
    else:
        # Провал! Штраф от 50% до 100% от суммы попытки (но не более баланса вора и строго > 0)
        fine = max(50, min(u_robber["balance"], int(amount * random.uniform(0.5, 1.0))))
        fine = max(1, fine)
        new_bal = await db.add_balance(robber_id, -fine, "rob_fail", str(uid))
        await db.add_balance(uid, fine, "rob_comp", str(robber_id))
        await message.reply(
            f"🚨 <b>Ограбление провалилось!</b>\n\n"
            f"{mention(message.from_user)} попался с поличным при попытке ограбить {mention_id(uid, name)}!\n"
            f"👮‍♂️ Полиция конфисковала и передала жертве компенсацию: <b>{money(fine)}</b> 💸\n\n"
            f"🪙 Ваш баланс: <b>{money(new_bal)}</b>")


@router.message(Cmd("скрыть мешок", "спрятать мешок", "спрятать карманы", "защита мешка", "hidebag", "hide_bag",
                    section=S_BONUS, usage="скрыть мешок", desc="Спрятать мешок от воров на 1-5 часов"))
async def cmd_hide_bag(message: Message, **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    hide_left = await db.cooldown_left(uid, "bag_hidden", 5 * 3600)
    if hide_left:

        return await message.reply(
            f"🛡 <b>Ваш мешок уже спрятан!</b>\n\n"
            f"Защита от ограблений действует ещё: <b>{hms(hide_left)}</b> 🔒")

    hours = random.randint(1, 5)
    dur = hours * 3600
    now = int(time.time())
    offset_ts = now - (5 * 3600 - dur)
    await db.execute(
        "INSERT INTO cooldowns (user_id, key, ts) VALUES (?, 'bag_hidden', ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET ts=?", (uid, offset_ts, offset_ts))

    await message.reply(
        f"🛡 <b>Вы спрятали свой мешок!</b>\n\n"
        f"🎲 Вам выпало случайное время защиты: <b>{hours} ч.</b>\n"
        f"В течение <b>{hours} часов</b> никто не сможет украсть ваши средства! 🔒")


# ---------- 14. Развлечения ----------
@router.message(Cmd("кто", section=S_FUN, usage="!кто {вопрос}",
                    desc="Случайный присутствующий участник (только с обращением)"))
async def cmd_who(message: Message, bot: Bot, args: str = "", **kw):
    """Отвечает только на явную команду с префиксом (!кто / кто); обычное «кто играть?» игнорируется."""
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type != "private":
        return

    q_low = (args or "").strip().lower()
    if q_low.startswith("админ") or q_low.startswith("модер"):
        from h_mod_ranks import cmd_staff
        return await cmd_staff(message, bot, **kw)
    if q_low.startswith("такой ") or q_low.startswith("такая "):
        from h_ai_features import cmd_ai_chat
        return await cmd_ai_chat(message, bot, args=f"кто {args}", **kw)

    q = html.escape(args) if args else "самый крутой"
    if message.chat.type == "private":

        return await message.reply(f"🤔 Кто {q}? Конечно ты!")

    rows = await members.known_chat_rows(message.chat.id, limit=100)
    me = await bot.me()
    people = await members.verified_members(
        bot, message.chat.id, rows, exclude=(me.id,))
    if not people:
        return await message.reply("Не нашёл присутствующих участников.")
    person = random.choice(people)
    who = members.summon_mention(
        person["user_id"], person.get("first_name"), person.get("username"))
    await message.reply(f"🤔 {q} — это {who}!")


@router.message(Cmd("шанс", "вероятность", section=S_FUN, usage="шанс {вопрос}",
                    desc="Вероятность события"))
async def cmd_chance(message: Message, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not args:
        if had_prefix or not in_group:
            return await message.reply("Формат: <code>шанс что я разбогатею</code>")
        return
    await message.reply(f"📊 Вероятность «{html.escape(args)}» — <b>{random.randint(0,100)}%</b>")


@router.message(Cmd("выбери", "выбор", section=S_FUN, usage="выбери а, б, в",
                    desc="Выбрать из вариантов"))
async def cmd_choose(message: Message, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    opts = [o.strip() for o in (args or "").replace(" или ", ",").split(",") if o.strip()]
    if len(opts) < 2:
        if had_prefix or not in_group:
            return await message.reply("Формат: <code>выбери чай, кофе</code>")
        return
    await message.reply(f"🎲 Я выбираю: <b>{html.escape(random.choice(opts))}</b>")


@router.message(Cmd("шар", "8ball", section=S_FUN, usage="шар {вопрос}",
                    desc="Магический шар"))
async def cmd_ball(message: Message, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    ans = ["Бесспорно", "Мне кажется — да", "Пока неясно", "Даже не думай",
           "Определённо нет", "Знаки говорят — да", "Весьма сомнительно", "Да", "Нет"]
    if not args:
        if had_prefix or not in_group:
            return await message.reply("Задайте вопрос: <code>шар мне повезёт?</code>")
        return
    await message.reply(f"🎱 {random.choice(ans)}")


@router.message(Cmd("рандом", "случайное число", section=S_FUN, usage="рандом 1 100",
                    desc="Случайное число"))
async def cmd_random(message: Message, args: str = "", **kw):
    p = (args or "").split()
    a, b = (int(p[0]), int(p[1])) if len(p) >= 2 and p[0].lstrip('-').isdigit() \
        and p[1].lstrip('-').isdigit() else (1, 100)
    await message.reply(f"🎲 Случайное число от {a} до {b}: <b>{random.randint(min(a,b), max(a,b))}</b>")


@router.message(Cmd("монетка", "монета", section=S_FUN, usage="монетка",
                    desc="Подбросить монетку"))
async def cmd_coin(message: Message, args: str = "", **kw):
    await message.reply(f"🪙 Выпал <b>{random.choice(['орёл', 'решка'])}</b>")


@router.message(Cmd("правда", "действие", "правда или действие", section=S_FUN,
                    usage="правда", desc="Правда или действие"))
async def cmd_truth(message: Message, **kw):
    truths = ["Какой твой самый большой страх?", "О чём ты жалеешь?",
              "Самый неловкий момент в жизни?", "Кому последнему ты врал?"]
    acts = ["Отправь последнее фото из галереи", "Напиши статус «я люблю бота» на час",
            "Позвони другу и спой", "Смени ник на «Монета» на сутки"]
    await message.reply(random.choice([f"❓ <b>Правда:</b> {random.choice(truths)}",
                                       f"🎬 <b>Действие:</b> {random.choice(acts)}"]))


@router.message(Cmd("анекдот", "шутка", section=S_FUN, usage="анекдот", desc="Случайный анекдот"))
async def cmd_joke(message: Message, **kw):
    jokes = [
        "— Как дела?\n— Как в сказке: чем дальше, тем страшнее.",
        "Программист ставит на тумбочку два стакана: с водой — если захочет пить, "
        "пустой — если не захочет.",
        "Лучший способ найти вещь — купить новую. Старая появится сразу.",
        "— Доктор, я живу в интернете!\n— Ясно. Перезагрузитесь.",
    ]
    await message.reply(f"😄 {random.choice(jokes)}")


@router.message(Cmd("погода", section=S_FUN, usage="погода {город}", desc="Шуточный прогноз"))
async def cmd_weather(message: Message, args: str = "", **kw):
    city = html.escape(args) if args else "у тебя дома"
    w = random.choice(["☀️ солнечно", "🌧 дождь", "❄️ снег", "⛅️ облачно", "🌪 ураган монет"])
    await message.reply(f"🌍 Погода в «{city}»: {w}, {random.randint(-20, 35)}°C")


# ---------- 15. Дуэли ----------
_duels: dict[str, dict] = {}


async def _bet_of(message: Message, raw: str, **kw) -> int | None:
    if not await topic_ok(message):
        return None
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    u = await db.get_user(message.from_user.id)
    bet = parse_amount(raw, u["balance"], MIN_BET)
    if not bet or bet < MIN_BET:
        if had_prefix or not in_group:
            await message.reply(f"Ставка от {money(MIN_BET)}.")
        return None
    if bet > MAX_BET:
        if had_prefix or not in_group:
            await message.reply(f"Максимум {money(MAX_BET)}.")
        return None
    if bet > u["balance"]:
        if had_prefix or not in_group:
            await message.reply(f"Недостаточно средств: {money(u['balance'])}.")
        return None
    return bet


# (PvP-Дуэли перенесены в полноценный модуль h_duels.py с экипировкой, критами и статами)



@router.message(Cmd("куб", "кубик", "кости", "cube", "dice", section=S_CUBE, usage="куб {ставка}",
                    desc="Бросить кубик на монеты"))
async def cmd_cube(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not args.strip():
        if had_prefix or not in_group:
            m = await message.answer_dice(emoji="🎲")
        return
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "cube", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "cube_bet")
        if message.chat.type in {"group", "supergroup"}:
            try:
                await db.add_to_chat_jackpot(message.chat.id, int(bet * 0.02))
            except Exception:
                pass
        m1 = await message.answer_dice(emoji="🎲")
        await asyncio.sleep(4)
        m2 = await message.answer_dice(emoji="🎲")
        await asyncio.sleep(4)
        p, b = m1.dice.value, m2.dice.value
        is_win = p > b
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        kb = make_game_replay_kb("cube", bet, message.from_user.id)
        if is_win:
            bal = await db.add_balance(message.from_user.id, bet * 2, "cube_win")
            await message.reply(f"🎲 {p} : {b} — <b>победа!</b> +{money(bet)}\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        elif p == b:
            bal = await db.add_balance(message.from_user.id, bet, "cube_draw")
            await message.reply(f"🎲 {p} : {b} — ничья.\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"🎲 {p} : {b} — проигрыш −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}", reply_markup=kb)
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("слоты", "slots", "казино", "казик", "казиныч", "casino", section=S_CUBE, usage="казик {ставка}",
                    desc="Игровые слоты (казино)"))
async def cmd_slots(message: Message, args: str = "", **kw):
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "slots", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "slots_bet")
        if message.chat.type in {"group", "supergroup"}:
            try:
                await db.add_to_chat_jackpot(message.chat.id, int(bet * 0.02))
            except Exception:
                pass
        m = await message.answer_dice(emoji="🎰")
        await asyncio.sleep(3.5)
        v = m.dice.value
        mult = 10 if v == 64 else (5 if v in (1, 22, 43) else (2 if v in (4, 8, 12, 16, 32, 48) else 0))
        is_win = mult > 0
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        kb = make_game_replay_kb("slots", bet, message.from_user.id)
        if v == 64:
            jackpot_won = 0
            if message.chat.type in {"group", "supergroup"}:
                try:
                    jackpot_won = await db.claim_chat_jackpot(message.chat.id, message.from_user.id, message.from_user.first_name)
                except Exception:
                    pass
            bal = await db.add_balance(message.from_user.id, bet * 10 + jackpot_won, "slots_jackpot_win")
            tag = (f"🔥 💥 <b>ДЖЕКПОТ ЧАТА СОРВАН!</b> 💥 🔥\n\n"
                   f"{mention(message.from_user)} выбил <b>7️⃣7️⃣7️⃣</b> (x10) и сорвал джекпот: <b>+{money(jackpot_won)}</b>!\n"
                   f"Общий выигрыш: <b>+{money(bet * 10 + jackpot_won)}</b> 🎉")
            try:
                await db.record_big_win(message.from_user.id, message.from_user.first_name, message.chat.id, "Слоты 🎰", bet, bet * 10 + jackpot_won)
            except Exception:
                pass
            await message.reply(f"{tag}\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        elif mult:
            bal = await db.add_balance(message.from_user.id, bet * mult, "slots_win")
            if bet * mult >= 10_000 or mult >= 5:
                try:
                    await db.record_big_win(message.from_user.id, message.from_user.first_name, message.chat.id, "Слоты 🎰", bet, bet * mult)
                except Exception:
                    pass
            await message.reply(f"🎰 <b>Выигрыш x{mult}!</b> +{money(bet*(mult-1))}\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"🎰 Мимо. −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}", reply_markup=kb)
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("дартс", "darts", section=S_CUBE, usage="дартс {ставка}",
                    desc="Дартс на монеты"))
async def cmd_darts(message: Message, args: str = "", **kw):
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "darts", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "darts_bet")
        if message.chat.type in {"group", "supergroup"}:
            try:
                await db.add_to_chat_jackpot(message.chat.id, int(bet * 0.02))
            except Exception:
                pass
        m = await message.answer_dice(emoji="🎯")
        await asyncio.sleep(3)
        v = m.dice.value
        mult = 5 if v == 6 else (2 if v in (4, 5) else (1 if v in (2, 3) else 0))
        is_win = mult > 1
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        kb = make_game_replay_kb("darts", bet, message.from_user.id)
        if mult > 1:
            bal = await db.add_balance(message.from_user.id, bet * mult, "darts_win")
            tag = "🎯 <b>В ЯБЛОЧКО! x5!</b>" if v == 6 else f"🎯 <b>Точное попадание! x{mult}!</b>"
            await message.reply(f"{tag} +{money(bet*(mult-1))}\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        elif mult == 1:
            bal = await db.add_balance(message.from_user.id, bet, "darts_draw")
            await message.reply(f"🎯 Возврат ставки (x1).\nБаланс: {money(bal)}{lvl_tag}", reply_markup=kb)
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"🎯 Мимо мишени! −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}", reply_markup=kb)
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("боулинг", "кегли", "bowling", section=S_CUBE, usage="боулинг {ставка}",
                    desc="Боулинг на монеты"))
async def cmd_bowling(message: Message, args: str = "", **kw):
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "bowling", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "bowling_bet")
        m = await message.answer_dice(emoji="🎳")
        await asyncio.sleep(3)
        v = m.dice.value
        mult = 4 if v == 6 else (2 if v in (4, 5) else 0)
        is_win = mult > 0
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        if mult:
            bal = await db.add_balance(message.from_user.id, bet * mult, "bowling_win")
            tag = "🎳 <b>СТРАЙК! x4!</b>" if v == 6 else f"🎳 <b>Отличный бросок! x{mult}!</b>"
            await message.reply(f"{tag} +{money(bet*(mult-1))}\nБаланс: {money(bal)}{lvl_tag}")
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"🎳 Шар в желобе! −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}")
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("футбол", "пенальти", "football", "penalty", section=S_CUBE, usage="футбол {ставка}",
                    desc="Пенальти на монеты"))
async def cmd_football(message: Message, args: str = "", **kw):
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "football", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "football_bet")
        m = await message.answer_dice(emoji="⚽")
        await asyncio.sleep(3)
        v = m.dice.value
        is_win = v in (3, 4, 5)
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        if is_win:
            win_amount = int(bet * 2.5)
            bal = await db.add_balance(message.from_user.id, win_amount, "football_win")
            await message.reply(f"⚽️ <b>ГОООЛ! x2.5!</b> +{money(win_amount - bet)}\nБаланс: {money(bal)}{lvl_tag}")
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"⚽️ Вратарь отбил мяч! −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}")
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("баскетбол", "basketball", section=S_CUBE, usage="баскетбол {ставка}",
                    desc="Баскетбол на монеты"))
async def cmd_basketball(message: Message, args: str = "", **kw):
    cur_g = is_in_game(message.from_user.id)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )
    bet = await _bet_of(message, args, **kw)
    if bet is None:
        return
    lock_game(message.from_user.id, "basketball", message.chat.id)
    try:
        await db.add_balance(message.from_user.id, -bet, "basketball_bet")
        m = await message.answer_dice(emoji="🏀")
        await asyncio.sleep(3)
        v = m.dice.value
        is_win = v in (3, 4, 5)
        lvl, lvl_up = await db.add_game_xp(message.from_user.id, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        if v in (4, 5):
            bal = await db.add_balance(message.from_user.id, bet * 3, "basketball_win")
            await message.reply(f"🏀 <b>Точно в корзину! x3!</b> +{money(bet * 2)}\nБаланс: {money(bal)}{lvl_tag}")
        elif v == 3:
            win_amount = int(bet * 1.5)
            bal = await db.add_balance(message.from_user.id, win_amount, "basketball_win")
            await message.reply(f"🏀 <b>Отскок от кольца! x1.5!</b> +{money(win_amount - bet)}\nБаланс: {money(bal)}{lvl_tag}")
        else:
            u = await db.get_user(message.from_user.id)
            await message.reply(f"🏀 Мимо кольца! −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}")
    finally:
        unlock_game(message.from_user.id)


@router.message(Cmd("рулетка", "roulette", section=S_CUBE, usage="рулетка [ставка] [выбор/числа/диапазон]",
                    desc="Рулетка: цвет/чёт/число/диапазоны (7-8, 1-8)/мульти-ставки"))
async def cmd_roulette(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    cur_g = is_in_game(uid)
    if cur_g:
        return await message.reply(
            f"⏳ <b>У вас уже идёт активная игра ({cur_g})!</b>\n"
            f"Дождитесь завершения текущего раунда, чтобы сделать новую ставку 🛑",
            disable_web_page_preview=True
        )

    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    raw_str = (args or "").strip()
    if not raw_str:
        if had_prefix or not in_group:
            return await message.reply(
                "🎡 <b>РУЛЕТКА</b> 🎰\n\n"
                "👉 <b>На цвет:</b> <code>рулетка 1000 красное</code> (или <code>чёрное</code>, x2)\n"
                "👉 <b>На чётность:</b> <code>рулетка 1000 чёт</code> (или <code>нечет</code>, x2)\n"
                "👉 <b>На диапазон / сплит:</b> <code>рулетка 1000 на 7-8</code> (x18), <code>рулетка 1000 на 1-8</code> (x4.5), <code>рулетка 1000 на 1-12</code> (x3)\n"
                "👉 <b>На точное число:</b> <code>рулетка 1000 на 17</code> (x36) или <code>зеро</code> (x36)\n"
                "👉 <b>Мульти-ставка:</b> <code>рулетка 1000 на 1 2 3 4 5 10 11 12</code> (ставка на каждое число)"
            )
        return

    import re
    # Разбиваем на токены, игнорируя союз/предлог 'на'
    tokens = [t.strip() for t in re.split(r"[\s,]+", raw_str) if t.strip() and t.lower() != "на"]
    if not tokens:
        return

    u = await db.get_user(uid)
    user_bal = u["balance"]

    # 1. Пытаемся найти ставку (первый или последний токен)
    bet = None
    bet_idx = None
    b_first = parse_amount(tokens[0], user_bal, MIN_BET)
    if b_first and not re.match(r"^\d+[-–—]\d+$", tokens[0]):
        if len(tokens) >= 2 and tokens[0].isdigit() and int(tokens[0]) <= 36:
            b_last = parse_amount(tokens[-1], user_bal, MIN_BET)
            if b_last and not (tokens[-1].isdigit() and int(tokens[-1]) <= 36):
                bet = b_last
                bet_idx = len(tokens) - 1
            else:
                bet = b_first
                bet_idx = 0
        else:
            bet = b_first
            bet_idx = 0
    else:
        b_last = parse_amount(tokens[-1], user_bal, MIN_BET)
        if b_last and not re.match(r"^\d+[-–—]\d+$", tokens[-1]):
            bet = b_last
            bet_idx = len(tokens) - 1

    if not bet:
        if had_prefix or not in_group:
            return await message.reply("⚠️ Укажите сумму ставки! Пример: <code>рулетка 1000 красное</code> или <code>рулетка 1000 на 7-8</code>")
        return

    # Остальные токены — это выбор цели
    target_tokens = [t for i, t in enumerate(tokens) if i != bet_idx]
    if not target_tokens:
        if had_prefix or not in_group:
            return await message.reply("⚠️ На что ставите? Укажите: <code>красное</code>, <code>чёрное</code>, <code>чёт</code>, <code>зеро</code>, число или диапазон (<code>7-8</code>)")
        return

    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

    bet_mode = ""
    bet_desc = ""
    range_bounds = None
    multi_nums = None
    single_num = None
    mult = 2.0
    total_cost = bet

    first_target = target_tokens[0].lower()
    m_range = re.match(r"^(\d+)[-–—](\d+)$", first_target)

    if m_range:
        a_n, b_n = int(m_range.group(1)), int(m_range.group(2))
        if a_n > b_n:
            a_n, b_n = b_n, a_n
        if a_n < 0 or b_n > 36:
            return await message.reply("⚠️ Числа рулетки от 0 до 36!")
        k = b_n - a_n + 1
        mult = 18.0 if k == 2 else (12.0 if k == 3 else (9.0 if k == 4 else (6.0 if k == 6 else (4.5 if k == 8 else (3.0 if k == 12 else (2.0 if k == 18 else round(36.0 / k, 1)))))))
        bet_mode = "range"
        range_bounds = (a_n, b_n)
        bet_desc = f"диапазон <b>{a_n}-{b_n}</b> (кэф <code>x{mult}</code>)"

    elif len(target_tokens) > 1 and all(t.isdigit() and 0 <= int(t) <= 36 for t in target_tokens):
        multi_nums = sorted(list(dict.fromkeys(int(t) for t in target_tokens)))
        total_cost = bet * len(multi_nums)
        mult = 36.0
        bet_mode = "multi"
        nums_str = ", ".join(str(n) for n in multi_nums)
        bet_desc = f"{len(multi_nums)} чисел ({nums_str}) по {money(bet)}"

    elif first_target in {"красное", "красн", "red"}:
        bet_mode = "color_red"
        mult = 2.0
        bet_desc = "<b>🔴 Красное</b> (кэф <code>x2</code>)"

    elif first_target in {"чёрное", "черное", "black"}:
        bet_mode = "color_black"
        mult = 2.0
        bet_desc = "<b>⚫️ Чёрное</b> (кэф <code>x2</code>)"

    elif first_target in {"чет", "чёт", "even"}:
        bet_mode = "even"
        mult = 2.0
        bet_desc = "<b>Чётное</b> (кэф <code>x2</code>)"

    elif first_target in {"нечет", "нечёт", "odd"}:
        bet_mode = "odd"
        mult = 2.0
        bet_desc = "<b>Нечётное</b> (кэф <code>x2</code>)"

    elif first_target in {"зеро", "zero"} or first_target == "0":
        bet_mode = "single"
        single_num = 0
        mult = 36.0
        bet_desc = "<b>🟢 Зеро (0)</b> (кэф <code>x36</code>)"

    elif first_target.isdigit() and 0 <= int(first_target) <= 36:
        single_num = int(first_target)
        mult = 36.0
        bet_mode = "single"
        clr = "🔴" if single_num in RED_NUMBERS else ("⚫️" if single_num > 0 else "🟢")
        bet_desc = f"число <b>{single_num} {clr}</b> (кэф <code>x36</code>)"

    else:
        if had_prefix or not in_group:
            return await message.reply("⚠️ Неизвестная ставка! Укажите: красное, чёрное, чёт, зеро, число (0-36) или диапазон (напр. <code>7-8</code>, <code>1-8</code>).")
        return

    if user_bal < total_cost:
        return await message.reply(
            f"Недостаточно средств!\nНужно: <b>{money(total_cost)}</b>, у вас: <b>{money(user_bal)}</b>"
        )

    lock_game(uid, "roulette", message.chat.id)
    try:
        await db.add_balance(uid, -total_cost, "roulette_bet")
        if message.chat.type in {"group", "supergroup"}:
            try:
                await db.add_to_chat_jackpot(message.chat.id, int(total_cost * 0.02))
            except Exception:
                pass

        user_label = mention(message.from_user)
        if bet_mode == "multi":
            lines = [f"🎰 <b>Ставка принята:</b> {user_label} {money(bet)} на <b>{n}</b>" for n in multi_nums[:25]]
            wait_msg = await message.reply("\n".join(lines) + f"\n\n🎡 <i>Рулетка раскручивается... Шарик брошен!</i>")
        else:
            wait_msg = await message.reply(
                f"🎰 <b>Ставка принята:</b> {user_label} <b>{money(total_cost)}</b> на {bet_desc}!\n\n"
                f"🎡 <i>Рулетка раскручивается... Шарик брошен!</i>"
            )

        await asyncio.sleep(3.0)

        win_num = random.randint(0, 36)
        if win_num == 0:
            clr_emoji = "🟢"
            clr_name = "зеро"
        elif win_num in RED_NUMBERS:
            clr_emoji = "🔴"
            clr_name = "красное"
        else:
            clr_emoji = "⚫️"
            clr_name = "чёрное"

        is_win = False
        payout = 0

        if bet_mode == "range":
            a_n, b_n = range_bounds
            if a_n <= win_num <= b_n:
                is_win = True
                payout = int(bet * mult)
        elif bet_mode == "multi":
            if win_num in multi_nums:
                is_win = True
                payout = int(bet * 36)
        elif bet_mode == "single":
            if win_num == single_num:
                is_win = True
                payout = int(bet * 36)
        elif bet_mode == "color_red" and clr_name == "красное":
            is_win = True
            payout = int(bet * 2)
        elif bet_mode == "color_black" and clr_name == "чёрное":
            is_win = True
            payout = int(bet * 2)
        elif bet_mode == "even" and win_num > 0 and win_num % 2 == 0:
            is_win = True
            payout = int(bet * 2)
        elif bet_mode == "odd" and win_num % 2 == 1:
            is_win = True
            payout = int(bet * 2)

        lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
        lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""

        replay_opt = f"{range_bounds[0]}-{range_bounds[1]}" if bet_mode == "range" else (str(single_num) if bet_mode == "single" else (first_target if bet_mode != "multi" else ""))
        kb = make_game_replay_kb("roulette", bet, uid, replay_opt) if replay_opt else None

        result_header = f"🎡 <b>Рулетка: {win_num}{clr_emoji} ({clr_name})</b>\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

        if is_win:
            net_profit = payout - total_cost
            new_bal = await db.add_balance(uid, payout, "roulette_win")
            if net_profit >= 15_000 or mult >= 5:
                try:
                    await db.record_big_win(uid, message.from_user.first_name, message.chat.id, f"Рулетка ({win_num}{clr_emoji})", total_cost, payout)
                except Exception:
                    pass
            card = (
                f"{result_header}"
                f"👤 Игрок: {user_label}\n"
                f"🎯 Ставка: {bet_desc}\n\n"
                f"🎉 <b>ПОБЕДА!</b> Выплата: <b>+{money(payout)}</b>\n"
                f"💰 Чистая прибыль: <b>+{money(net_profit)}</b>\n"
                f"🪙 Баланс: <b>{money(new_bal)}</b>{lvl_tag}"
            )
        else:
            u_now = await db.get_user(uid)
            card = (
                f"{result_header}"
                f"👤 Игрок: {user_label}\n"
                f"🎯 Ставка: {bet_desc}\n\n"
                f"💔 <b>Проигрыш: −{money(total_cost)}</b>\n"
                f"🪙 Баланс: <b>{money(u_now['balance'])}</b>{lvl_tag}"
            )

        try:
            await wait_msg.edit_text(card, reply_markup=kb)
        except Exception:
            await message.reply(card, reply_markup=kb)
    finally:
        unlock_game(uid)


# Прямой ввод ставки в рулетку без ключевого слова (например «1000 на 7-8», «23000000 11 12 14 13...»)
@router.message(F.text.regexp(r"^(?:([\d\s]+)\s+на\s+(\d+[-–—]\d+|красн\w*|ч[её]рн\w*|зеро|0|[1-9]\d*)|(\d{3,})\s+((?:\b(?:[0-9]|[12][0-9]|3[0-6])\b\s*){2,}))\s*$", flags=re.IGNORECASE))
async def cmd_roulette_direct(message: Message, **kw):
    if not await topic_ok(message):
        return
    text = (message.text or "").strip()
    return await cmd_roulette(message, args=text, **kw)


@router.message(Cmd("джекпот", "казик джекпот", "джекпот чата", "куш", section=S_CUBE,
                    usage="джекпот", desc="Посмотреть накопленный джекпот чата"))
async def cmd_chat_jackpot(message: Message, **kw):
    chat_id = message.chat.id
    jk = await db.get_chat_jackpot(chat_id)
    pool = jk.get("pool", 5000)
    last_winner = jk.get("last_winner_name")
    last_amount = jk.get("last_winner_amount", 0)

    lines = [
        f"🔥 <b>НАКОПИТЕЛЬНЫЙ ДЖЕКПОТ КАЗИНО</b> 🎰\n",
        f"💰 <b>Банк джекпота беседы:</b> <code>{money(pool)}</code>\n",
        f"✨ <i>С каждой ставки игроков в казино 2% отчисляется в общий накопительный банк!</i>",
        f"🎯 <b>Как сорвать куш:</b> выбейте комбинацию <b>7️⃣7️⃣7️⃣</b> в слотах (<code>казик 1000</code>).",
    ]
    if last_winner and last_amount:
        lines.append(f"\n👑 <b>Последний победитель:</b> {last_winner} (+{money(last_amount)})")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎰 Крутить слоты (1 000 🪙)", callback_data=f"grep:slots:1000:{message.from_user.id}:")
    ]])
    await message.reply("\n".join(lines), reply_markup=kb)


# ---------- Инлайн-кнопки быстрого повтора (Реплей) для Казино и Игр ----------
@router.callback_query(F.data.startswith("grep:"))
async def cb_game_replay(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    if len(parts) < 4:
        return await call.answer("Неверные данные.")
    game_code = parts[1]
    bet = int(parts[2])
    target_uid = int(parts[3])
    opt = parts[4] if len(parts) > 4 else ""

    if call.from_user.id != target_uid:
        return await call.answer("Это не ваша игра! Напишите казик 1000 для своей игры 😉", show_alert=True)

    if game_code == "close":
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return await call.answer("Выигрыш на вашем балансе! 💰")

    if game_code == "jackpot":
        chat_id = call.message.chat.id
        jk = await db.get_chat_jackpot(chat_id)
        pool = jk.get("pool", 5000)
        last_winner = jk.get("last_winner_name")
        last_amt = jk.get("last_winner_amount", 0)
        txt = f"🔥 Накопительный джекпот чата: {money(pool)}!\n\nС каждой ставки отчисляется 2% в общий куш.\nВыпадает при 7️⃣7️⃣7️⃣ в слотах!"
        if last_winner and last_amt:
            txt += f"\n\n👑 Последний куш: {last_winner} (+{money(last_amt)})"
        return await call.answer(txt, show_alert=True)

    if not await topic_ok(call.message):
        return await call.answer("Казино отключено в этом чате или теме.", show_alert=True)

    if game_code == "bj":
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        from h_grams import start_quick_blackjack
        return await start_quick_blackjack(call, bet)

    if game_code == "race":
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        from h_grams import start_quick_race
        h_idx = int(opt) if opt and opt.isdigit() else 1
        return await start_quick_race(call, bet, h_idx)

    active = is_in_game(call.from_user.id)
    if active:
        return await call.answer(f"⏳ Вы уже играете в {active}! Дождитесь завершения раунда.", show_alert=True)

    bal = await db.get_balance(call.from_user.id)
    if bal < bet:
        return await call.answer(f"Недостаточно средств!\nНужно: {money(bet)}, у вас: {money(bal)}", show_alert=True)

    lock_game(call.from_user.id, game_code, call.message.chat.id)
    try:
        # Списание ставки
        await db.add_balance(call.from_user.id, -bet, f"{game_code}_bet")
        if call.message.chat.type in {"group", "supergroup"}:
            try:
                await db.add_to_chat_jackpot(call.message.chat.id, int(bet * 0.02))
            except Exception:
                pass

        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        if game_code == "slots":
            await call.answer("🎰 Крутим барабан!")
            m = await call.message.answer_dice(emoji="🎰")
            await asyncio.sleep(3.5)
            v = m.dice.value
            mult = 10 if v == 64 else (5 if v in (1, 22, 43) else (2 if v in (4, 8, 12, 16, 32, 48) else 0))
            is_win = mult > 0
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if v == 64:
                jackpot_won = 0
                if call.message.chat.type in {"group", "supergroup"}:
                    try:
                        jackpot_won = await db.claim_chat_jackpot(call.message.chat.id, call.from_user.id, call.from_user.first_name)
                    except Exception:
                        pass
                new_bal = await db.add_balance(call.from_user.id, bet * 10 + jackpot_won, "slots_jackpot_win")
                try:
                    await db.record_big_win(call.from_user.id, call.from_user.first_name, call.message.chat.id, "Слоты 🎰", bet, bet * 10 + jackpot_won)
                except Exception:
                    pass
                msg_text = (
                    f"🔥 💥 <b>ДЖЕКПОТ ЧАТА СОРВАН!</b> 💥 🔥\n\n"
                    f"{mention(call.from_user)} выбил <b>7️⃣7️⃣7️⃣</b> (x10) и сорвал джекпот: <b>+{money(jackpot_won)}</b>!\n"
                    f"Всего выигрыш: <b>+{money(bet * 10 + jackpot_won)}</b> 🎉\n"
                    f"Баланс: {money(new_bal)}{lvl_tag}"
                )
            elif mult:
                new_bal = await db.add_balance(call.from_user.id, bet * mult, "slots_win")
                if bet * mult >= 10_000 or mult >= 5:
                    try:
                        await db.record_big_win(call.from_user.id, call.from_user.first_name, call.message.chat.id, "Слоты 🎰", bet, bet * mult)
                    except Exception:
                        pass
                msg_text = f"🎰 <b>Выигрыш x{mult}!</b> +{money(bet*(mult-1))}\nБаланс: {money(new_bal)}{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🎰 Мимо. −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("slots", bet, call.from_user.id))

        elif game_code == "cube":
            await call.answer("🎲 Бросаем кубики!")
            m1 = await call.message.answer_dice(emoji="🎲")
            await asyncio.sleep(3.5)
            m2 = await call.message.answer_dice(emoji="🎲")
            await asyncio.sleep(3.5)
            p, b = m1.dice.value, m2.dice.value
            is_win = p > b
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if is_win:
                new_bal = await db.add_balance(call.from_user.id, bet * 2, "cube_win")
                msg_text = f"🎲 {p} : {b} — <b>победа!</b> +{money(bet)}\nБаланс: {money(new_bal)}{lvl_tag}"
            elif p == b:
                new_bal = await db.add_balance(call.from_user.id, bet, "cube_draw")
                msg_text = f"🎲 {p} : {b} — ничья.\nБаланс: {money(new_bal)}{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🎲 {p} : {b} — проигрыш −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("cube", bet, call.from_user.id))

        elif game_code == "darts":
            await call.answer("🎯 Бросаем дротик!")
            m = await call.message.answer_dice(emoji="🎯")
            await asyncio.sleep(3)
            v = m.dice.value
            mult = 5 if v == 6 else (2 if v in (4, 5) else (1 if v in (2, 3) else 0))
            is_win = mult > 1
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if mult > 1:
                new_bal = await db.add_balance(call.from_user.id, bet * mult, "darts_win")
                tag = "🎯 <b>В ЯБЛОЧКО! x5!</b>" if v == 6 else f"🎯 <b>Точное попадание! x{mult}!</b>"
                msg_text = f"{tag} +{money(bet*(mult-1))}\nБаланс: {money(new_bal)}{lvl_tag}"
            elif mult == 1:
                new_bal = await db.add_balance(call.from_user.id, bet, "darts_draw")
                msg_text = f"🎯 Возврат ставки (x1).\nБаланс: {money(new_bal)}{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🎯 Мимо мишени! −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("darts", bet, call.from_user.id))

        elif game_code == "coin":
            side = opt if opt in ("орёл", "решка") else "орёл"
            await call.answer(f"🪙 Бросаем на {side}!")
            flip = random.choice(["орёл", "решка"])
            is_win = (flip == side)
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if is_win:
                new_bal = await db.add_balance(call.from_user.id, bet * 2, "coin_win")
                msg_text = f"🪙 Выпал <b>{flip}</b>!\n\n🎉 <b>ПОБЕДА! +{money(bet)}</b>\nБаланс: <b>{money(new_bal)}</b>{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🪙 Выпал <b>{flip}</b>\n\n💔 Проигрыш −{money(bet)}\nБаланс: <b>{money(u['balance'])}</b>{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("coin", bet, call.from_user.id, side))

        elif game_code == "wheel":
            await call.answer("🎡 Крутим барабан!")
            from h_grams import WHEEL_SECTORS
            weights = [30, 25, 20, 12, 7, 4, 1.5, 0.5]
            mult, label = random.choices(WHEEL_SECTORS, weights=weights, k=1)[0]
            is_win = mult > 1.0
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if mult > 0:
                win = int(bet * mult)
                new_bal = await db.add_balance(call.from_user.id, win, "wheel_win")
                diff = win - bet
                res = (f"🎉 <b>+{money(diff)}</b>" if diff > 0 else (f"🔸 Возврат" if diff == 0 else f"💔 −{money(-diff)}"))
                msg_text = f"🎡 Сектор: <b>{label}</b>\n\n{res}\nБаланс: <b>{money(new_bal)}</b>{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🎡 Сектор: <b>{label}</b>\n\n💔 Проигрыш −{money(bet)}\nБаланс: <b>{money(u['balance'])}{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("wheel", bet, call.from_user.id))

        elif game_code == "roulette":
            choice = opt.lower() if opt else "красное"
            await call.answer(f"🎡 Ставка на {choice}!")
            num = random.randint(0, 36)
            red = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
            color = "зеро" if num == 0 else ("красное" if num in red else "чёрное")
            mult = 0.0
            if choice in {"красное", "красн", "red"} and color == "красное": mult = 2.0
            elif choice in {"чёрное", "черное", "black"} and color == "чёрное": mult = 2.0
            elif choice in {"чет", "чёт", "even"} and num and num % 2 == 0: mult = 2.0
            elif choice in {"нечет", "нечёт", "odd"} and num % 2 == 1: mult = 2.0
            elif choice in {"зеро", "zero"} and num == 0: mult = 36.0
            elif choice.isdigit() and int(choice) == num: mult = 36.0
            elif "-" in choice:
                p = choice.split("-")
                if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
                    a, b = int(p[0]), int(p[1])
                    if min(a, b) <= num <= max(a, b):
                        k = abs(b - a) + 1
                        mult = round(36.0 / max(1, k), 1)

            is_win = mult > 0
            lvl, lvl_up = await db.add_game_xp(call.from_user.id, 1, is_win=is_win)
            lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
            if mult:
                win_amt = int(bet * mult)
                new_bal = await db.add_balance(call.from_user.id, win_amt, "roulette_win")
                if win_amt >= 10_000 or mult >= 10:
                    try:
                        await db.record_big_win(call.from_user.id, call.from_user.first_name, call.message.chat.id, "Рулетка 🎡", bet, win_amt)
                    except Exception:
                        pass
                msg_text = f"🎡 Выпало <b>{num} {color}</b> — x{mult}: +{money(win_amt - bet)}\nБаланс: {money(new_bal)}{lvl_tag}"
            else:
                u = await db.get_user(call.from_user.id)
                msg_text = f"🎡 Выпало <b>{num} {color}</b> — проигрыш −{money(bet)}\nБаланс: {money(u['balance'])}{lvl_tag}"

            return await call.message.reply(msg_text, reply_markup=make_game_replay_kb("roulette", bet, call.from_user.id, choice))
    finally:
        unlock_game(call.from_user.id)


@router.message(Cmd("топ заносов", "топ казик", "турнир казик", "заносы", "турнир казино", "бигвин", "бигвины",
                    section=S_BONUS, usage="топ заносов",
                    desc="Турнирная таблица крупнейших заносов и выигрышей недели в казино"))
async def cmd_casino_top_wins(message: Message, **kw):
    wins = await db.get_weekly_big_wins(limit=10)
    if not wins:
        return await message.reply(
            "🎰 <b>ТУРНИР КАЗИНО MOXXI: ТОП ЗАНОСОВ</b> 🏆\n"
            "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
            "На этой неделе пока нет зафиксированных крупных заносов!\n\n"
            "Крутите <code>казик [ставка]</code>, выбивайте 777 и попадайте в зал славы казино!"
        )

    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    for i, w in enumerate(wins):
        med = medals[i]
        uname = w["user_name"] or f"Игрок {w['user_id']}"
        lines.append(f"{med} {mention_id(w['user_id'], uname)} — <b>+{money(w['max_win'])}</b> ({w['game_name']}, ставка: {money(w['bet'])})")

    card = (
        "🎰 🏆 <b>ТУРНИР КАЗИНО: ТОП ЗАНОСОВ НЕДЕЛИ</b> 🏆 🎰\n"
        "✦ ══ • ⊰ 💎 🍀 🔥 🎰 🎲 🪙 ⊱ • ══ ✦\n\n"
        "Лидеры по самому крупному выигрышу за последние 7 дней:\n\n"
        + "\n".join(lines) +
        "\n\n🔥 <i>Испытай удачу: <code>казик 1000</code> / <code>слоты 1к</code>!</i>"
    )
    await message.reply(card)


# ---------- Магазин и топ дня (работают и в группе, и в личке) ----------
@router.message(Cmd("магазин", "shop", section=S_BONUS,
                    usage="магазин", desc="Магазин статусов и монет"))
async def cmd_shop(message: Message, **kw):
    from h_vip import SHOP_HUB_TEXT, shop_hub_keyboard
    await message.reply(SHOP_HUB_TEXT, reply_markup=shop_hub_keyboard(), disable_web_page_preview=True)


@router.message(Cmd("топ дня", "топдня", "актив дня", section=9, usage="топ дня",
                    desc="Самые активные за сегодня"))
async def cmd_topday(message: Message, **kw):
    import time as _t
    day = _t.strftime("%Y-%m-%d")
    if message.chat.type == "private":
        rows = await db.fetchall(
            "SELECT d.user_id, SUM(d.messages) m, u.first_name FROM daily_stats d "
            "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.day=? "
            "GROUP BY d.user_id ORDER BY m DESC LIMIT 10", (day,))
    else:
        rows = await db.fetchall(
            "SELECT d.user_id, d.messages m, u.first_name FROM daily_stats d "
            "LEFT JOIN users u ON u.user_id=d.user_id WHERE d.day=? AND d.chat_id=? "
            "ORDER BY m DESC LIMIT 10", (day, message.chat.id))
    if not rows:
        return await message.reply("🏆 Сегодня ещё никто не активничал.")
    medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
    await message.reply("🏆 <b>Топ дня</b>\n\n" + "\n".join(
        f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — {r['m']} сообщ."
        for i, r in enumerate(rows)))


# ══════════════════ ЕЖЕДНЕВНОЕ КОЛЕСО ФОРТУНЫ МОКСИ ══════════════════

@router.message(Cmd("колесо", "рулетка дня", "фортуна", "колесо фортуны", "крутить колесо",
                    section=S_BONUS, usage="колесо",
                    desc="🎡 Ежедневное Колесо Фортуны Мокси (1 бесплатная крутка в день)"))
async def cmd_wheel_of_fortune(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    left = await db.cooldown_left(uid, "wheel_of_fortune", 86400)
    if left:
        return await message.reply(
            f"🎡 ✨ <b>КОЛЕСО ФОРТУНЫ МОКСИ</b> ✨ 🎡\n\n"
            f"💋 Детка, ты уже забирал свой ежедневный подарок сегодня!\n"
            f"Следующая бесплатная крутка будет доступна через: <b>{hms(left)}</b>."
        )

    # Ставим кулдаун на 24 часа
    await db.set_cooldown(uid, "wheel_of_fortune")

    anim = await message.reply(
        "🎡 ✨ <b>КОЛЕСО ФОРТУНЫ МОКСИ</b> ✨ 🎡\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "🎰 <i>Раскручиваем барабан арены...</i>\n"
        "<code>[ 🪙 750 | 💎 3500 | 🧪 Зелье | 👑 VIP | 🍖 Корм | 🪙 1500 ]</code>"
    )
    await asyncio.sleep(1.2)

    # Розыгрыш приза
    roll = random.random()
    if roll < 0.05:  # 5% ДЖЕКПОТ: VIP-статус на сутки!
        await db.execute(
            "INSERT INTO vip (user_id, until, level) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET until = MAX(until, ?) + 86400, level = MAX(level, 1)",
            (uid, int(time.time()) + 86400, int(time.time()))
        )
        prize_text = "👑 <b>ДЖЕКПОТ АРЕНЫ: VIP-СТАТУС НА 24 ЧАСА!</b> 👑\n<i>Все бонусы и привилегии VIP активированы!</i>"
    elif roll < 0.20:  # 15%: 3500 монет
        bal = await db.add_balance(uid, 3500, "wheel_reward")
        prize_text = f"💎 <b>БОЛЬШОЙ КУШ: +3 500 {money(3500)}!</b>\nБаланс: {money(bal)}"
    elif roll < 0.45:  # 25%: 1500 монет
        bal = await db.add_balance(uid, 1500, "wheel_reward")
        prize_text = f"🪙 <b>ОТЛИЧНЫЙ КУШ: +1 500 {money(1500)}!</b>\nБаланс: {money(bal)}"
    elif roll < 0.60:  # 15%: Зелье лечения
        try:
            import h_items
            await h_items.add_inventory_item(uid, "medkit", 1)
            prize_text = "🧪 <b>РЕДКОЕ ЛЕЧЕБНОЕ ЗЕЛЬЕ РЕЙДА!</b>\n<i>Добавлено в инвентарь для битв с боссами.</i>"
        except Exception:
            bal = await db.add_balance(uid, 1000, "wheel_reward")
            prize_text = f"🪙 <b>+1 000 {money(1000)}!</b>\nБаланс: {money(bal)}"
    elif roll < 0.75:  # 15%: Премиум-корм
        try:
            import h_items
            await h_items.add_inventory_item(uid, "pet_food", 2)
            prize_text = "🍖 <b>ПРЕМИУМ-КОРМ ДЛЯ ПИТОМЦА (x2)!</b>\n<i>Ваш питомец будет сыт и доволен.</i>"
        except Exception:
            bal = await db.add_balance(uid, 1000, "wheel_reward")
            prize_text = f"🪙 <b>+1 000 {money(1000)}!</b>\nБаланс: {money(bal)}"
    else:  # 25%: 750 монет
        bal = await db.add_balance(uid, 750, "wheel_reward")
        prize_text = f"🪙 <b>ПРИЗ: +750 {money(750)}!</b>\nБаланс: {money(bal)}"

    res_card = (
        f"🎡 ✨ <b>КОЛЕСО ФОРТУНЫ МОКСИ</b> ✨ 🎡\n"
        f"✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦\n\n"
        f"🎉 <b>Стрелка остановилась! Твой выигрыш:</b>\n\n"
        f"{prize_text}\n\n"
        f"💋 <i>Приходи завтра за следующей бесплатной круткой!</i> 🍸✨"
    )
    try:
        await anim.edit_text(res_card)
    except Exception:
        await message.reply(res_card)

