"""🏰 Клановые Войны, Казна, Прокачка Базы Клана (Оружейная, Казначейство, Форпост)."""
from __future__ import annotations

import html
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import require
from core_registry import Cmd
from utils import mention, mention_id, money, parse_amount

router = Router(name="clan_wars")
S = 17  # Раздел кланов

# Стоимость и бонусы прокачки зданий базы
BUILDING_COSTS = {
    "armory": {
        "name": "🏛️ Оружейная",
        "desc": "+5% к урону всех членов клана по Боссам за уровень (макс. 5 ур.)",
        "prices": [15000, 35000, 75000, 150000, 300000]
    },
    "treasury": {
        "name": "🏦 Казначейство",
        "desc": "Увеличивает ежедневный доход клана на +500 монет за уровень (макс. 5 ур.)",
        "prices": [10000, 25000, 50000, 100000, 200000]
    },
    "outpost": {
        "name": "🛡️ Форпост",
        "desc": "+10% защиты и очков войн кланов за уровень (макс. 5 ур.)",
        "prices": [12000, 30000, 60000, 120000, 250000]
    }
}


async def _get_clan_by_user(user_id: int) -> dict | None:
    member = await db.fetchone("SELECT clan_id FROM clan_members WHERE user_id=?", (user_id,))
    if not member:
        return None
    return await db.fetchone("SELECT * FROM clans WHERE id=?", (member["clan_id"],))


async def _get_clan_upgrades(clan_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM clan_upgrades WHERE clan_id=?", (clan_id,))
    if not row:
        await db.execute("INSERT OR IGNORE INTO clan_upgrades (clan_id) VALUES (?)", (clan_id,))
        return {"armory_lvl": 0, "treasury_lvl": 0, "outpost_lvl": 0}
    return dict(row)


@router.message(Cmd("база клана", "клан база", "база", section=S, rank=0,
                    usage="база клана", desc="🏰 Просмотр и прокачка зданий базы клана"))
async def cmd_clan_base(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане! Создать клан: <code>создать клан {имя}</code>")

    cid = clan["id"]
    upg = await _get_clan_upgrades(cid)

    text = [
        f"🏰 ✨ <b>ШТАБ-КВАРТИРА КЛАНА «{html.escape(clan['name'])}»</b> ✨ 🏰",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"💰 Казна клана: <b>{money(clan['balance'])}</b>\n",
        "<b>Здания базы и их уровни:</b>"
    ]

    for b_key, b_info in BUILDING_COSTS.items():
        lvl = upg.get(f"{b_key}_lvl", 0)
        max_lvl = len(b_info["prices"])
        next_cost = money(b_info["prices"][lvl]) if lvl < max_lvl else "МАКС. УРОВЕНЬ"
        text.append(
            f"• <b>{b_info['name']}</b>: <b>{lvl}/{max_lvl} ур.</b>\n"
            f"   └─▸ <i>{b_info['desc']}</i>\n"
            f"   └─▸ Улучшение: <code>{next_cost}</code>\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Улучшить здание:</i> <code>прокачать оружейную</code>, <code>прокачать банк</code>, <code>прокачать форпост</code>")
    text.append("💰 <i>Пополнить казну:</i> <code>вклад 1000</code>")

    await message.reply("\n".join(text))


@router.message(Cmd("прокачать", "улучшить базу", "прокачать базу", section=S, rank=0,
                    usage="прокачать [здание]", desc="⬆️ Улучшить здание на базе клана"))
async def cmd_upgrade_building(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    # Проверка, является ли лидером клана
    if clan["owner_id"] != uid:
        return await message.reply("👑 Улучшать базу клана может только Лидер клана!")

    a = (args or "").strip().lower()
    b_key = None
    if "оруж" in a or "атак" in a or "1" in a:
        b_key = "armory"
    elif "банк" in a or "казн" in a or "2" in a:
        b_key = "treasury"
    elif "форпост" in a or "защит" in a or "3" in a:
        b_key = "outpost"

    if not b_key:
        return await message.reply(
            "🏰 <b>Укажите здание для улучшения:</b>\n"
            "• <code>прокачать оружейную</code>\n"
            "• <code>прокачать банк</code>\n"
            "• <code>прокачать форпост</code>"
        )

    cid = clan["id"]
    upg = await _get_clan_upgrades(cid)
    lvl_field = f"{b_key}_lvl"
    cur_lvl = upg.get(lvl_field, 0)
    b_info = BUILDING_COSTS[b_key]

    if cur_lvl >= len(b_info["prices"]):
        return await message.reply(f"⭐️ <b>{b_info['name']}</b> уже прокачана до максимального уровня!")

    cost = b_info["prices"][cur_lvl]
    if clan["balance"] < cost:
        return await message.reply(
            f"❌ В казне клана недостаточно средств! Нужно <b>{money(cost)}</b>, а в казне <b>{money(clan['balance'])}</b>.\n"
            f"Пополнить казну: <code>вклад {cost - clan['balance']}</code>"
        )

    # Списываем из казны и поднимаем уровень
    await db.execute("UPDATE clans SET balance = balance - ? WHERE id=?", (cost, cid))
    await db.execute(f"UPDATE clan_upgrades SET {lvl_field} = {lvl_field} + 1 WHERE clan_id=?", (cid,))

    new_lvl = cur_lvl + 1
    await message.reply(
        f"🎉 🏰 <b>ЗДАНИЕ УСПЕШНО УЛУЧШЕНО!</b> 🏰 🎉\n\n"
        f"Здание: <b>{b_info['name']}</b>\n"
        f"Новый уровень: <b>⭐ {new_lvl}/{len(b_info['prices'])}</b>\n"
        f"Списано из казны: <b>{money(cost)}</b>\n"
        f"Эффект: <i>{b_info['desc']}</i>"
    )


@router.message(Cmd("вклад", "пополнить казну", "клан вклад", section=S, rank=0,
                    usage="вклад {сумма}", desc="💰 Пополнить казну своего клана"))
async def cmd_clan_deposit(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    amt = parse_amount(args.strip()) if args else 0
    if amt <= 0:
        return await message.reply("Формат: <code>вклад 5000</code>")

    user = await db.get_user(uid)
    if user["balance"] < amt:
        return await message.reply(f"❌ У вас недостаточно монет! Баланс: <b>{money(user['balance'])}</b>.")

    await db.add_balance(uid, -amt)
    await db.execute("UPDATE clans SET balance = balance + ? WHERE id=?", (amt, clan["id"]))
    await db.add_xp(message.chat.id, uid, int(amt / 100))

    new_c = await db.fetchone("SELECT balance FROM clans WHERE id=?", (clan["id"],))
    await message.reply(
        f"💰 ✨ <b>ВКЛАД В КАЗНУ КЛАНА УСПЕШЕН!</b> ✨ 💰\n\n"
        f"👤 Внёс: {mention(message.from_user)}\n"
        f"💵 Сумма: <b>+{money(amt)}</b>\n"
        f"🏦 Новая казна клана «{html.escape(clan['name'])}»: <b>{money(new_c['balance'])}</b>"
    )


@router.message(Cmd("топ кланов", "кланы топ", section=S, rank=0,
                    usage="топ кланов", desc="🏆 Рейтинг сильнейших кланов"))
async def cmd_top_clans(message: Message, bot: Bot, **kw):
    rows = await db.fetchall(
        "SELECT c.id, c.name, c.balance, COUNT(m.user_id) as members_count, "
        "COALESCE(u.armory_lvl, 0) + COALESCE(u.treasury_lvl, 0) + COALESCE(u.outpost_lvl, 0) as total_lvl "
        "FROM clans c "
        "LEFT JOIN clan_members m ON m.clan_id=c.id "
        "LEFT JOIN clan_upgrades u ON u.clan_id=c.id "
        "GROUP BY c.id ORDER BY total_lvl DESC, c.balance DESC LIMIT 10"
    )
    if not rows:
        return await message.reply("🏰 Кланов пока нет. Создайте первый: <code>создать клан {имя}</code>")

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = [
        "🏰 ✨ <b>ТОП СИЛЬНЕЙШИХ КЛАНОВ</b> ✨ 🏰",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    for i, r in enumerate(rows):
        icon = medals[i] if i < len(medals) else "▫️"
        cname = html.escape(r["name"])
        text.append(
            f"{icon} <b>«{cname}»</b> — База: <b>⭐ {r['total_lvl']} ур.</b> · Состав: <b>{r['members_count']} чел.</b>\n"
            f"   └─▸ Казна: 💰 <b>{money(r['balance'])}</b>\n"
        )

    text.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    text.append("💡 <i>Штаб своего клана:</i> <code>база клана</code>")
    await message.reply("\n".join(text))
