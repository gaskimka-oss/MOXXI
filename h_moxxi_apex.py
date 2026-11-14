"""🌟 Флагманский модуль расширения функционала MOXXI 3.5 APEX UPDATE.

Новые масштабные системы:
1. 🐉 Клановые Рейд-Боссы (Clan Raids):
   - «клан босс» / «рейд клана» — статус здоровья босса, таймер, топ урона бойцов;
   - «атаковать босса» / «бить босса» — нанесение сокрушительного урона с кулдауном;
   - «призвать босса» — призыв следующего тира рейд-босса (Виверн -> Колосс -> Пожиратель -> Левиафан -> Бог Разлома);
   - Инлайн-кнопки боя и авто-награды в казну клана и личный баланс.

2. 👥 Клановый Состав и Иерархия Ролей:
   - «клан состав» — древовидный ростер участников с ролями (Глава, Зам, Полководец, Ветеран, Боец) и уроном;
   - «клан зам @user» — назначение заместителя Главы клана;
   - «клан кик @user» — исключение бойца из клана;
   - «клан девиз [текст]» — официальный девиз клана.

3. 📜 Клановые Контракты и Квесты:
   - «клан квесты» / «клан контракты» — 3 ежедневных общих задания для клана с прогрессом;
   - «собрать контракт [1/2/3]» — получение щедрых наград в казну, опыта и кристаллов.

4. ⚔️ Война Кланов (Clan Wars PvP):
   - «война кланов [имя]» / «битва кланов» — масштабная битва двух кланов за влияние и процент от казны соперника.

5. 🌟 Социальная Карма и Респекты:
   - «+реп [@user] [причина]» / «респект [@user]» / «похвалить [@user]» — повышение репутации и отзыв;
   - «-реп [@user] [причина]» — снижение репутации за неадекватное поведение;
   - «респекты [@user]» — карточка отзывов и звания уважения в чате.
"""
from __future__ import annotations

import asyncio
import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import db
from core_ranks import effective_rank, require
from core_registry import Cmd
from core_resolve import real_reply, resolve_target
from utils import mention, mention_id, money, parse_amount

router = Router(name="moxxi_apex")
S_CLAN = 17  # Раздел кланов
S_SOCIAL = 21  # Социальный раздел

BOSS_TIERS = {
    1: {"name": "Древний Виверн", "icon": "🐉", "hp": 150000, "reward": 60000, "xp": 500, "crystals": 0},
    2: {"name": "Обсидиановый Колосс", "icon": "🗿", "hp": 350000, "reward": 150000, "xp": 1000, "crystals": 2},
    3: {"name": "Пожиратель Миров", "icon": "👾", "hp": 750000, "reward": 350000, "xp": 2500, "crystals": 5},
    4: {"name": "Кибер-Левиафан", "icon": "⚡", "hp": 1500000, "reward": 750000, "xp": 5000, "crystals": 10},
    5: {"name": "Тёмный Бог Разлома", "icon": "🌌", "hp": 3000000, "reward": 1500000, "xp": 10000, "crystals": 25},
}

ROLE_LABELS = {
    "owner": "👑 Глава Клана",
    "deputy": "🔱 Заместитель",
    "general": "⚔️ Полководец",
    "veteran": "🛡️ Ветеран",
    "member": "🗡️ Боец"
}

# В памяти кулдауны респектов: user_id -> [ts1, ts2, ...]
REP_TIMESTAMPS: dict[int, list[int]] = {}


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


async def _get_or_create_clan_boss(clan_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM clan_bosses WHERE clan_id=?", (clan_id,))
    if not row:
        b = BOSS_TIERS[1]
        now = int(time.time())
        await db.execute(
            "INSERT INTO clan_bosses (clan_id, boss_name, boss_icon, max_hp, current_hp, level, spawned_ts, defeated) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, 0)",
            (clan_id, b["name"], b["icon"], b["hp"], b["hp"], now)
        )
        row = await db.fetchone("SELECT * FROM clan_bosses WHERE clan_id=?", (clan_id,))
    return dict(row)


def _make_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return "░" * length
    pct = max(0.0, min(1.0, current / maximum))
    filled = int(round(pct * length))
    return "█" * filled + "░" * (length - filled)


# ═════════════════════════════════════════════════════════════════════
# 1. 🐉 КЛАНОВЫЕ РЕЙД-БОССЫ (CLAN RAIDS)
# ═════════════════════════════════════════════════════════════════════

@router.message(Cmd("клан босс", "босс клана", "рейд клана", "клановый босс", "рейд", section=S_CLAN, rank=0,
                    usage="клан босс", desc="🐉 Просмотр текущего рейд-босса клана"))
async def cmd_clan_boss(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане! Создать клан: <code>создать клан {имя}</code>")

    cid = clan["id"]
    boss = await _get_or_create_clan_boss(cid)
    lvl = boss["level"]
    b_tier = BOSS_TIERS.get(lvl, BOSS_TIERS[5])

    damagers = await db.fetchall(
        "SELECT h.user_id, h.total_damage, u.first_name FROM clan_boss_hits h "
        "LEFT JOIN users u ON u.user_id=h.user_id WHERE h.clan_id=? ORDER BY h.total_damage DESC LIMIT 5",
        (cid,)
    )

    hp_bar = _make_hp_bar(boss["current_hp"], boss["max_hp"], length=12)
    pct = int(round((boss["current_hp"] / boss["max_hp"]) * 100)) if boss["max_hp"] > 0 else 0

    lines = [
        f"🏰 ✨ <b>РЕЙД-БОСС КЛАНА «{html.escape(clan['name'])}»</b> ✨ 🏰",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"{boss['boss_icon']} <b>{boss['boss_name']}</b> [⭐ {lvl} Уровень]",
        f"Здоровье: <code>[{hp_bar}]</code> <b>{pct}%</b>",
        f"❤️ HP: <b>{boss['current_hp']:,}</b> / <b>{boss['max_hp']:,}</b>".replace(",", " "),
        f"💰 Награда в казну при победе: <b>+{money(b_tier['reward'])}</b>",
    ]
    if b_tier["crystals"] > 0:
        lines.append(f"💎 Бонус: <b>+{b_tier['crystals']} кристаллов</b> соклановцам")

    lines.append("\n🏆 <b>Топ урона соклановцев:</b>")
    if damagers:
        for idx, d in enumerate(damagers):
            m_icon = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx]
            u_name = mention_id(d["user_id"], d["first_name"] or str(d["user_id"]))
            lines.append(f"{m_icon} {u_name} — <b>{d['total_damage']:,}</b> урона".replace(",", " "))
    else:
        lines.append("<i>Пока никто не нанёс урон. Будьте первым!</i>")

    lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    if boss["current_hp"] > 0:
        lines.append("⚔️ <i>Нанести удар:</i> <code>атаковать босса</code> или кнопка ниже")
    else:
        lines.append("🎉 <i>Босс повержен! Лидер может призвать следующего:</i> <code>призвать босса</code>")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Нанести удар по боссу", callback_data=f"clan_boss:hit:{cid}")],
        [InlineKeyboardButton(text="🏰 База клана", callback_data=f"clan_boss:base:{cid}")]
    ])
    await message.reply("\n".join(lines), reply_markup=kb)


@router.message(Cmd("атаковать босса", "бить босса", "удар по боссу", "атака босса", section=S_CLAN, rank=0,
                    usage="атаковать босса", desc="⚔️ Нанести сокрушительный удар по клановому боссу"))
async def cmd_attack_clan_boss(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    boss = await _get_or_create_clan_boss(cid)

    if boss["current_hp"] <= 0:
        return await message.reply("🎉 Текущий босс уже повержен! Лидер клана может призвать нового: <code>призвать босса</code>")

    vip_lvl, _, vip_active = await db.get_vip_info(uid)
    cooldown_secs = 1800 if (vip_active and vip_lvl >= 1) else 3600

    now = int(time.time())
    last_hit = await db.fetchone(
        "SELECT last_hit_ts FROM clan_boss_hits WHERE clan_id=? AND user_id=?",
        (cid, uid)
    )
    if last_hit and last_hit["last_hit_ts"] > 0:
        passed = now - last_hit["last_hit_ts"]
        if passed < cooldown_secs:
            rem = cooldown_secs - passed
            rem_m = rem // 60
            rem_s = rem % 60
            return await message.reply(f"⏳ Ваши силы восстанавливаются! До следующей атаки: <b>{rem_m} мин {rem_s} сек</b>.")

    upg = await _get_clan_upgrades(cid)
    armory_bonus = upg.get("armory_lvl", 0) * 800

    base_dmg = random.randint(2500, 5500) + armory_bonus
    is_crit = (random.random() < 0.20)
    if is_crit:
        base_dmg = int(base_dmg * 2.2)

    try:
        user_pet = await db.get_user_pet(uid)
        if user_pet:
            base_dmg += user_pet["level"] * 150
    except Exception:
        pass

    dmg = min(boss["current_hp"], base_dmg)
    new_hp = max(0, boss["current_hp"] - dmg)

    await db.execute(
        "INSERT INTO clan_boss_hits (clan_id, user_id, total_damage, last_hit_ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(clan_id, user_id) DO UPDATE SET total_damage=total_damage + excluded.total_damage, last_hit_ts=excluded.last_hit_ts",
        (cid, uid, dmg, now)
    )
    await db.execute("UPDATE clan_bosses SET current_hp=? WHERE clan_id=?", (new_hp, cid))

    coin_reward = max(100, int(dmg * 0.08))
    xp_reward = max(15, int(dmg // 100))
    await db.add_balance(uid, coin_reward, "clan_boss_hit")
    await db.add_xp(message.chat.id, uid, xp_reward)

    crit_badge = " 🔥 <b>КРИТИЧЕСКИЙ УДАР x2.2!</b>" if is_crit else ""
    u_mention = mention(message.from_user)

    if new_hp == 0:
        lvl = boss["level"]
        b_tier = BOSS_TIERS.get(lvl, BOSS_TIERS[5])
        clan_reward = b_tier["reward"]
        await db.execute("UPDATE clans SET balance = balance + ? WHERE id=?", (clan_reward, cid))
        await db.execute("UPDATE clan_bosses SET defeated=1 WHERE clan_id=?", (cid,))

        win_txt = (
            f"🎉 💥 <b>РЕЙД-БОСС «{boss['boss_name']}» ПОВЕРЖЕН!</b> 💥 🎉\n\n"
            f"🗡 Решающий удар нанёс: {u_mention} (<b>-{dmg:,} HP</b>{crit_badge})\n\n"
            f"💰 Казна клана пополнена на: <b>+{money(clan_reward)}</b>!\n"
            f"✨ Опыт участников клана увеличен!\n"
            f"🏆 Доступен следующий уровень рейда! Лидер клана может призвать нового босса: <code>призвать босса</code>"
        )
        return await message.reply(win_txt)

    hp_bar = _make_hp_bar(new_hp, boss["max_hp"], length=10)
    txt = (
        f"⚔️ {u_mention} нанёс сокрушительный удар по боссу <b>{boss['boss_name']}</b>!\n\n"
        f"💥 Урон: <b>-{dmg:,} HP</b>{crit_badge}\n"
        f"❤️ Осталось HP: <code>[{hp_bar}]</code> <b>{new_hp:,}</b> / <b>{boss['max_hp']:,}</b>\n"
        f"💵 Награда бойцу: <b>+{money(coin_reward)}</b> · <b>+{xp_reward} XP</b>\n"
        f"⏳ Следующий удар через 1 час."
    ).replace(",", " ")
    await message.reply(txt)


@router.callback_query(F.data.startswith("clan_boss:hit:"))
async def cb_clan_boss_hit(cq: CallbackQuery, bot: Bot):
    uid = cq.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await cq.answer("🏰 Вы не состоите в этом клане!", show_alert=True)

    cid = clan["id"]
    boss = await _get_or_create_clan_boss(cid)
    if boss["current_hp"] <= 0:
        return await cq.answer("🎉 Босс уже повержен! Лидер может призвать нового.", show_alert=True)

    vip_lvl, _, vip_active = await db.get_vip_info(uid)
    cooldown_secs = 1800 if (vip_active and vip_lvl >= 1) else 3600
    now = int(time.time())

    last_hit = await db.fetchone(
        "SELECT last_hit_ts FROM clan_boss_hits WHERE clan_id=? AND user_id=?",
        (cid, uid)
    )
    if last_hit and last_hit["last_hit_ts"] > 0:
        passed = now - last_hit["last_hit_ts"]
        if passed < cooldown_secs:
            rem_m = (cooldown_secs - passed) // 60
            return await cq.answer(f"⏳ Силы восстанавливаются! До удара: {rem_m} мин.", show_alert=True)

    upg = await _get_clan_upgrades(cid)
    armory_bonus = upg.get("armory_lvl", 0) * 800
    base_dmg = random.randint(2500, 5500) + armory_bonus
    is_crit = (random.random() < 0.20)
    if is_crit:
        base_dmg = int(base_dmg * 2.2)

    dmg = min(boss["current_hp"], base_dmg)
    new_hp = max(0, boss["current_hp"] - dmg)

    await db.execute(
        "INSERT INTO clan_boss_hits (clan_id, user_id, total_damage, last_hit_ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(clan_id, user_id) DO UPDATE SET total_damage=total_damage + excluded.total_damage, last_hit_ts=excluded.last_hit_ts",
        (cid, uid, dmg, now)
    )
    await db.execute("UPDATE clan_bosses SET current_hp=? WHERE clan_id=?", (new_hp, cid))
    coin_reward = max(100, int(dmg * 0.08))
    await db.add_balance(uid, coin_reward, "clan_boss_hit")

    alert_txt = f"⚔️ Удар нанесён: -{dmg:,} HP! Получено: +{money(coin_reward)}"
    if is_crit:
        alert_txt = "🔥 КРИТ! " + alert_txt

    await cq.answer(alert_txt, show_alert=True)


@router.message(Cmd("призвать босса", "новый босс", "клан новый босс", section=S_CLAN, rank=0,
                    usage="призвать босса", desc="🐉 Призвать нового рейд-босса клана"))
async def cmd_summon_clan_boss(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    cm = await db.fetchone("SELECT role FROM clan_members WHERE clan_id=? AND user_id=?", (cid, uid))
    is_lead = (clan["owner_id"] == uid) or (cm and cm.get("role") == "deputy")
    if not is_lead:
        return await message.reply("👑 Призывать нового босса могут Лидер или Заместитель клана!")

    boss = await _get_or_create_clan_boss(cid)
    if boss["current_hp"] > 0:
        return await message.reply(f"⚠️ Текущий босс <b>{boss['boss_name']}</b> ещё жив! Сначала добейте его: <code>клан босс</code>")

    new_lvl = min(len(BOSS_TIERS), boss["level"] + 1)
    b_tier = BOSS_TIERS[new_lvl]
    now = int(time.time())

    await db.execute("DELETE FROM clan_boss_hits WHERE clan_id=?", (cid,))
    await db.execute(
        "UPDATE clan_bosses SET boss_name=?, boss_icon=?, max_hp=?, current_hp=?, level=?, spawned_ts=?, defeated=0 WHERE clan_id=?",
        (b_tier["name"], b_tier["icon"], b_tier["hp"], b_tier["hp"], new_lvl, now, cid)
    )

    await message.reply(
        f"🌌 ⚡ <b>ПРИЗВАН НОВЫЙ РЕЙД-БОСС КЛАНА!</b> ⚡ 🌌\n\n"
        f"{b_tier['icon']} <b>{b_tier['name']}</b> [Уровень ⭐ {new_lvl}]\n"
        f"❤️ HP: <b>{b_tier['hp']:,}</b>\n"
        f"💰 Награда при победе: <b>+{money(b_tier['reward'])}</b> в казну!\n\n"
        f"⚔️ <i>Объявите всеобщий сбор клана! Начать атаку:</i> <code>атаковать босса</code>"
    )


# ═════════════════════════════════════════════════════════════════════
# 2. 👥 КЛАНОВЫЙ СОСТАВ И УПРАВЛЕНИЕ РОЛЯМИ
# ═════════════════════════════════════════════════════════════════════

@router.message(Cmd("клан состав", "состав клана", "соклановцы", section=S_CLAN, rank=0,
                    usage="клан состав", desc="👥 Полный список участников клана и их звания"))
async def cmd_clan_roster(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    members = await db.fetchall(
        "SELECT m.user_id, m.role, m.ts, u.first_name, u.username, "
        "COALESCE(h.total_damage, 0) as boss_dmg "
        "FROM clan_members m "
        "LEFT JOIN users u ON u.user_id=m.user_id "
        "LEFT JOIN clan_boss_hits h ON h.clan_id=m.clan_id AND h.user_id=m.user_id "
        "WHERE m.clan_id=? ORDER BY "
        "CASE m.role WHEN 'owner' THEN 1 WHEN 'deputy' THEN 2 WHEN 'general' THEN 3 WHEN 'veteran' THEN 4 ELSE 5 END, "
        "boss_dmg DESC",
        (cid,)
    )

    lines = [
        f"🏰 ✨ <b>СОСТАВ КЛАНА «{html.escape(clan['name'])}»</b> ✨ 🏰",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"👥 Всего участников: <b>{len(members)} чел.</b>\n"
    ]

    for m in members:
        role_title = ROLE_LABELS.get(m.get("role", "member"), "🗡️ Боец")
        m_link = mention_id(m["user_id"], m["first_name"] or str(m["user_id"]))
        dmg_str = f" · 💥 <i>{m['boss_dmg']:,} урона</i>" if m["boss_dmg"] > 0 else ""
        lines.append(f"• {role_title}: {m_link}{dmg_str}")

    lines.append("\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    lines.append("💡 <i>Назначить зама:</i> <code>клан зам @user</code> · <i>Исключить:</i> <code>клан кик @user</code>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)


@router.message(Cmd("клан зам", "клан назначить зам", "назначить зам клана", section=S_CLAN, rank=0,
                    usage="клан зам @user", desc="🔱 Назначить заместителя главы клана"))
async def cmd_clan_deputy(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan or clan["owner_id"] != uid:
        return await message.reply("👑 Назначать заместителя может только Глава клана!")

    tgt_id, tgt_name, _ = await resolve_target(message, args, bot)
    if not tgt_id:
        return await message.reply("Укажите участника клана: <code>клан зам @user</code>")

    cid = clan["id"]
    in_clan = await db.fetchone("SELECT 1 FROM clan_members WHERE clan_id=? AND user_id=?", (cid, tgt_id))
    if not in_clan:
        return await message.reply("Этот игрок не состоит в вашем клане!")

    await db.execute("UPDATE clan_members SET role='deputy' WHERE clan_id=? AND user_id=?", (cid, tgt_id))
    await message.reply(
        f"🎉 {mention_id(tgt_id, tgt_name)} назначен <b>🔱 Заместителем Главы Клана «{html.escape(clan['name'])}»</b>!"
    )


@router.message(Cmd("клан кик", "клан выгнать", "выгнать из клана", section=S_CLAN, rank=0,
                    usage="клан кик @user", desc="🚪 Исключить участника из клана"))
async def cmd_clan_kick(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    my_m = await db.fetchone("SELECT role FROM clan_members WHERE clan_id=? AND user_id=?", (cid, uid))
    is_lead = (clan["owner_id"] == uid) or (my_m and my_m.get("role") == "deputy")
    if not is_lead:
        return await message.reply("⛔️ Исключать участников могут только Лидер и Заместитель клана!")

    tgt_id, tgt_name, _ = await resolve_target(message, args, bot)
    if not tgt_id:
        return await message.reply("Укажите пользователя: <code>клан кик @user</code>")

    if tgt_id == clan["owner_id"]:
        return await message.reply("Нельзя исключить создателя клана!")

    in_clan = await db.fetchone("SELECT role FROM clan_members WHERE clan_id=? AND user_id=?", (cid, tgt_id))
    if not in_clan:
        return await message.reply("Этот пользователь не состоит в вашем клане.")

    if in_clan.get("role") == "deputy" and clan["owner_id"] != uid:
        return await message.reply("Заместителя может исключить только Создатель клана!")

    await db.execute("DELETE FROM clan_members WHERE clan_id=? AND user_id=?", (cid, tgt_id))
    await message.reply(f"👋 {mention_id(tgt_id, tgt_name)} исключён из клана <b>«{html.escape(clan['name'])}»</b>.")


@router.message(Cmd("клан девиз", "девиз клана", section=S_CLAN, rank=0,
                    usage="клан девиз [текст]", desc="🛡 Установить официальный девиз клана"))
async def cmd_clan_motto(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    if clan["owner_id"] != uid:
        return await message.reply("👑 Менять девиз может только Глава клана!")

    motto_text = (args or "").strip()[:64]
    if not motto_text:
        return await message.reply("Укажите текст девиза: <code>клан девиз Честь и отвага!</code>")

    await db.execute("UPDATE clans SET motto=? WHERE id=?", (motto_text, cid))
    await message.reply(f"🛡 <b>Девиз клана установлен:</b> <i>«{html.escape(motto_text)}»</i>")


# ═════════════════════════════════════════════════════════════════════
# 3. 📜 КЛАНОВЫЕ КОНТРАКТЫ И КВЕСТЫ
# ═════════════════════════════════════════════════════════════════════

@router.message(Cmd("клан квесты", "клан контракты", "квесты клана", "контракты клана", section=S_CLAN, rank=0,
                    usage="клан квесты", desc="📜 Ежедневные задания и контракты для клана"))
async def cmd_clan_quests(message: Message, bot: Bot, **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    now_day = int(time.time()) // 86400

    q = await db.fetchone("SELECT * FROM clan_quests WHERE clan_id=?", (cid,))
    if not q or q["quest_day"] != now_day:
        await db.execute(
            "INSERT INTO clan_quests (clan_id, quest_day, q1_done, q2_done, q3_done, q1_claimed, q2_claimed, q3_claimed) "
            "VALUES (?, ?, 0, 0, 0, 0, 0, 0) "
            "ON CONFLICT(clan_id) DO UPDATE SET quest_day=excluded.quest_day, "
            "q1_done=0, q2_done=0, q3_done=0, q1_claimed=0, q2_claimed=0, q3_claimed=0",
            (cid, now_day)
        )
        q = await db.fetchone("SELECT * FROM clan_quests WHERE clan_id=?", (cid,))

    hits_cnt_row = await db.fetchone("SELECT COUNT(*) c FROM clan_boss_hits WHERE clan_id=?", (cid,))
    hits_cnt = hits_cnt_row["c"] if hits_cnt_row else 0

    upg = await _get_clan_upgrades(cid)
    total_upg = upg.get("armory_lvl", 0) + upg.get("treasury_lvl", 0) + upg.get("outpost_lvl", 0)

    q1_ok = hits_cnt >= 5
    q2_ok = clan["balance"] >= 25000
    q3_ok = total_upg >= 3

    lines = [
        f"🏰 ✨ <b>ЕЖЕДНЕВНЫЕ КОНТРАКТЫ КЛАНА «{html.escape(clan['name'])}»</b> ✨ 🏰",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"1. ⚔️ <b>Охота на Босса:</b> Совершить 5 ударов соклановцами ({hits_cnt}/5)",
        f"   └─▸ Статус: {'✅ Выполнен' if q1_ok else '⏳ В процессе'} · Награда: <b>+25 000 в казну</b>\n",
        f"2. 💰 <b>Богатство Клана:</b> Накопить от 25,000 монет в казне ({clan['balance']:,}/25 000)",
        f"   └─▸ Статус: {'✅ Выполнен' if q2_ok else '⏳ В процессе'} · Награда: <b>+1 💎 Кристалл</b>\n",
        f"3. 🏛️ <b>Укрепление Цитадели:</b> Прокачать базу суммарно до 3 ур. ({total_upg}/3)",
        f"   └─▸ Статус: {'✅ Выполнен' if q3_ok else '⏳ В процессе'} · Награда: <b>+50 очков рейтинга</b>\n",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        "💡 <i>Собрать награду:</i> <code>собрать контракт [номер]</code>"
    ]
    await message.reply("\n".join(lines))


@router.message(Cmd("собрать контракт", "забрать контракт", section=S_CLAN, rank=0,
                    usage="собрать контракт [1/2/3]", desc="🎁 Собрать награду за выполненный контракт клана"))
async def cmd_claim_clan_quest(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan = await _get_clan_by_user(uid)
    if not clan:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid = clan["id"]
    now_day = int(time.time()) // 86400
    q = await db.fetchone("SELECT * FROM clan_quests WHERE clan_id=? AND quest_day=?", (cid, now_day))
    if not q:
        return await message.reply("Контракты ещё не обновлены. Проверьте: <code>клан квесты</code>")

    q_num = args.strip()
    if q_num == "1":
        if q["q1_claimed"]:
            return await message.reply("Награда за 1-й контракт уже получена сегодня!")
        hits = await db.fetchone("SELECT COUNT(*) c FROM clan_boss_hits WHERE clan_id=?", (cid,))
        if (hits["c"] if hits else 0) < 5:
            return await message.reply("Контракт ещё не выполнен! Нужно сделать 5 ударов по клан-боссу.")
        await db.execute("UPDATE clans SET balance = balance + 25000 WHERE id=?", (cid,))
        await db.execute("UPDATE clan_quests SET q1_claimed=1 WHERE clan_id=?", (cid,))
        return await message.reply("🎉 Контракт #1 выполнен! В казну клана начислено <b>+25 000 монет</b>!")
    elif q_num == "2":
        if q["q2_claimed"]:
            return await message.reply("Награда за 2-й контракт уже получена сегодня!")
        if clan["balance"] < 25000:
            return await message.reply("Контракт ещё не выполнен! В казне должно быть от 25 000 монет.")
        await db.add_crystals(uid, 1)
        await db.execute("UPDATE clan_quests SET q2_claimed=1 WHERE clan_id=?", (cid,))
        return await message.reply("🎉 Контракт #2 выполнен! Вам начислен <b>+1 💎 Кристалл</b>!")
    elif q_num == "3":
        if q["q3_claimed"]:
            return await message.reply("Награда за 3-й контракт уже получена сегодня!")
        upg = await _get_clan_upgrades(cid)
        if (upg.get("armory_lvl", 0) + upg.get("treasury_lvl", 0) + upg.get("outpost_lvl", 0)) < 3:
            return await message.reply("Контракт ещё не выполнен! Суммарный уровень базы должен быть от 3.")
        await db.execute("UPDATE clan_quests SET q3_claimed=1 WHERE clan_id=?", (cid,))
        return await message.reply("🎉 Контракт #3 выполнен! Клану начислено <b>+50 очков рейтинга</b>!")
    else:
        return await message.reply("Укажите номер контракта: <code>собрать контракт 1</code>, <code>2</code> или <code>3</code>")


# ═════════════════════════════════════════════════════════════════════
# 4. ⚔️ ВОЙНА КЛАНОВ (CLAN WARS PVP)
# ═════════════════════════════════════════════════════════════════════

@router.message(Cmd("война кланов", "клан война", "битва кланов", section=S_CLAN, rank=0,
                    usage="война кланов [имя_клана]", desc="⚔️ Бросить вызов другому клану на битву"))
async def cmd_clan_war_challenge(message: Message, bot: Bot, args: str = "", **kw):
    uid = message.from_user.id
    clan1 = await _get_clan_by_user(uid)
    if not clan1:
        return await message.reply("🏰 Вы не состоите в клане!")

    cid1 = clan1["id"]
    if clan1["owner_id"] != uid:
        cm = await db.fetchone("SELECT role FROM clan_members WHERE clan_id=? AND user_id=?", (cid1, uid))
        if not cm or cm.get("role") != "deputy":
            return await message.reply("👑 Начать войну кланов могут только Глава или Заместитель!")

    target_name = (args or "").strip()
    if not target_name:
        return await message.reply("Укажите имя вражеского клана: <code>война кланов {имя}</code>\nПосмотреть соперников: <code>топ кланов</code>")

    clan2 = await db.fetchone("SELECT * FROM clans WHERE lower(name)=lower(?)", (target_name,))
    if not clan2:
        return await message.reply(f"Клан «{html.escape(target_name)}» не найден!")

    cid2 = clan2["id"]
    if cid1 == cid2:
        return await message.reply("Нельзя объявить войну собственному клану!")

    if clan1["balance"] < 10000 or clan2["balance"] < 10000:
        return await message.reply("Для войны оба клана должны иметь в казне минимум <b>10 000 монет</b>!")

    upg1 = await _get_clan_upgrades(cid1)
    upg2 = await _get_clan_upgrades(cid2)

    m1 = await db.fetchone("SELECT COUNT(*) c FROM clan_members WHERE clan_id=?", (cid1,))
    m2 = await db.fetchone("SELECT COUNT(*) c FROM clan_members WHERE clan_id=?", (cid2,))

    power1 = (upg1.get("armory_lvl", 0) * 2500) + (upg1.get("outpost_lvl", 0) * 3000) + (m1["c"] * 1000) + random.randint(1000, 5000)
    power2 = (upg2.get("armory_lvl", 0) * 2500) + (upg2.get("outpost_lvl", 0) * 3000) + (m2["c"] * 1000) + random.randint(1000, 5000)

    if power1 >= power2:
        winner, loser = clan1, clan2
        spoils = max(1000, int(clan2["balance"] * 0.05))
        await db.execute("UPDATE clans SET balance = balance + ? WHERE id=?", (spoils, cid1))
        await db.execute("UPDATE clans SET balance = balance - ? WHERE id=?", (spoils, cid2))
    else:
        winner, loser = clan2, clan1
        spoils = max(1000, int(clan1["balance"] * 0.05))
        await db.execute("UPDATE clans SET balance = balance - ? WHERE id=?", (spoils, cid1))
        await db.execute("UPDATE clans SET balance = balance + ? WHERE id=?", (spoils, cid2))

    now = int(time.time())
    await db.execute(
        "INSERT INTO clan_wars_history (clan1_id, clan2_id, winner_id, spoils, ts) VALUES (?, ?, ?, ?, ?)",
        (cid1, cid2, winner["id"], spoils, now)
    )

    txt = (
        f"⚔️ 💥 <b>БИТВА КЛАНОВ ЗАВЕРШЕНА!</b> 💥 ⚔️\n\n"
        f"🏰 Атакующий: <b>«{html.escape(clan1['name'])}»</b> [Мощь: <b>{power1:,}</b>]\n"
        f"🏰 Защитник: <b>«{html.escape(clan2['name'])}»</b> [Мощь: <b>{power2:,}</b>]\n\n"
        f"🏆 <b>ПОБЕДИТЕЛЬ: КЛАН «{html.escape(winner['name'])}»!</b>\n"
        f"💰 Трофеи войны: <b>+{money(spoils)}</b> переведено в казну победителя!\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"💡 <i>Прокачивайте оружейную и форпост для повышения мощи в войне: <code>база клана</code></i>"
    ).replace(",", " ")
    await message.reply(txt)


# ═════════════════════════════════════════════════════════════════════
# 5. 🌟 СОЦИАЛЬНАЯ КАРМА И РЕСПЕКТЫ
# ═════════════════════════════════════════════════════════════════════

def _can_give_rep(uid: int) -> bool:
    now = int(time.time())
    ts_list = REP_TIMESTAMPS.get(uid, [])
    # Очищаем метки старше 24 часов
    ts_list = [t for t in ts_list if now - t < 86400]
    REP_TIMESTAMPS[uid] = ts_list
    return len(ts_list) < 3


def _record_rep_given(uid: int):
    now = int(time.time())
    ts_list = REP_TIMESTAMPS.setdefault(uid, [])
    ts_list.append(now)


@router.message(Cmd("+реп", "+rep", "респект", "похвалить", section=S_SOCIAL, rank=0,
                    usage="+реп @user [причина]", desc="⭐️ Выразить респект и повысить репутацию участника"))
async def cmd_give_rep(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    tgt_id, tgt_name, rest = await resolve_target(message, args, bot)

    if not tgt_id:
        return await message.reply("Укажите пользователя: <code>+реп @user [причина]</code>")

    if tgt_id == sender_id:
        return await message.reply("❌ Нельзя ставить респект самому себе!")

    tgt_user = await db.get_user(tgt_id)
    if not tgt_user or tgt_user["banned"]:
        return await message.reply("Пользователь не найден или заблокирован.")

    if not _can_give_rep(sender_id):
        return await message.reply("⏳ Вы исчерпали дневной лимит респектов (макс. 3 в сутки). Приходите завтра!")

    reason = (rest or "Отличный участник беседы!").strip()[:64]
    _record_rep_given(sender_id)

    # Обновляем репутацию
    await db.execute("UPDATE users SET rep = rep + 1 WHERE user_id=?", (tgt_id,))
    now = int(time.time())
    await db.execute(
        "INSERT INTO user_reputation_logs (from_id, to_id, delta, reason, chat_id, ts) VALUES (?, ?, 1, ?, ?, ?)",
        (sender_id, tgt_id, reason, message.chat.id, now)
    )

    new_u = await db.get_user(tgt_id)
    sender_mention = mention(message.from_user)
    tgt_mention = mention_id(tgt_id, tgt_name)

    await message.reply(
        f"⭐️ ✨ <b>РЕСПЕКТ ВЫРАЖЕН!</b> ✨ ⭐️\n\n"
        f"👤 {sender_mention} повысил репутацию {tgt_mention}!\n"
        f"💬 Отзыв: <i>«{html.escape(reason)}»</i>\n"
        f"📈 Новая репутация: <b>{new_u['rep']}</b> ⭐\n\n"
        f"💡 <i>Посмотреть все отзывы:</i> <code>респекты @user</code>"
    )


@router.message(Cmd("-реп", "-rep", "дизреспект", section=S_SOCIAL, rank=0,
                    usage="-реп @user [причина]", desc="👎 Снизить репутацию нарушителя"))
async def cmd_take_rep(message: Message, bot: Bot, args: str = "", **kw):
    sender_id = message.from_user.id if message.from_user else 0
    tgt_id, tgt_name, rest = await resolve_target(message, args, bot)

    if not tgt_id:
        return await message.reply("Укажите пользователя: <code>-реп @user [причина]</code>")

    if tgt_id == sender_id:
        return await message.reply("❌ Нельзя ставить дизреспект самому себе!")

    if not _can_give_rep(sender_id):
        return await message.reply("⏳ Вы исчерпали дневной лимит респектов (макс. 3 в сутки).")

    reason = (rest or "Неподобающее поведение").strip()[:64]
    _record_rep_given(sender_id)

    await db.execute("UPDATE users SET rep = rep - 1 WHERE user_id=?", (tgt_id,))
    now = int(time.time())
    await db.execute(
        "INSERT INTO user_reputation_logs (from_id, to_id, delta, reason, chat_id, ts) VALUES (?, ?, -1, ?, ?, ?)",
        (sender_id, tgt_id, reason, message.chat.id, now)
    )

    new_u = await db.get_user(tgt_id)
    sender_mention = mention(message.from_user)
    tgt_mention = mention_id(tgt_id, tgt_name)

    await message.reply(
        f"👎 <b>РЕПУТАЦИЯ СНИЖЕНА!</b>\n\n"
        f"👤 {sender_mention} выразил дизреспект {tgt_mention}!\n"
        f"Причина: <i>«{html.escape(reason)}»</i>\n"
        f"📉 Текущая репутация: <b>{new_u['rep']}</b> ⭐"
    )


@router.message(Cmd("респекты", "отзывы", "карпа", "моя репутация", section=S_SOCIAL, rank=0,
                    usage="респекты [@user]", desc="📜 Посмотреть историю отзывов и уровень уважения"))
async def cmd_view_rep_logs(message: Message, bot: Bot, args: str = "", **kw):
    tgt_id = message.from_user.id if message.from_user else 0
    tgt_name = message.from_user.first_name if message.from_user else "Игрок"

    from core_resolve import real_reply
    if args or real_reply(message) is not None:
        uid, name, _ = await resolve_target(message, args, bot)
        if uid:
            tgt_id = uid
            tgt_name = name or str(uid)

    user = await db.get_user(tgt_id)
    rep_val = user["rep"] if user else 0

    if rep_val >= 50:
        badge = "👑 Абсолютная Легенда"
    elif rep_val >= 25:
        badge = "💎 Почётный Ветеран"
    elif rep_val >= 10:
        badge = "🌟 Уважаемый Участник"
    elif rep_val >= 0:
        badge = "▫️ Рядовой Игрок"
    else:
        badge = "⚠️ Нарушитель на заметке"

    logs = await db.fetchall(
        "SELECT l.*, u.first_name FROM user_reputation_logs l "
        "LEFT JOIN users u ON u.user_id=l.from_id "
        "WHERE l.to_id=? ORDER BY l.id DESC LIMIT 5",
        (tgt_id,)
    )

    lines = [
        f"⭐️ ✨ <b>КАРТОЧКА РЕПУТАЦИИ: {mention_id(tgt_id, tgt_name)}</b> ✨ ⭐️",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        f"📊 Очки репутации: <b>{rep_val} ⭐</b>",
        f"🏅 Статус в обществе: <b>{badge}</b>\n",
        "💬 <b>Последние отзывы участников:</b>"
    ]

    if logs:
        for item in logs:
            sign = "➕" if item["delta"] > 0 else "➖"
            author = mention_id(item["from_id"], item["first_name"] or str(item["from_id"]))
            reason = html.escape(item["reason"] or "Без комментария")
            lines.append(f"{sign} От {author}: <i>«{reason}»</i>")
    else:
        lines.append("<i>Пока никто не оставлял отзывов. Будьте первым: <code>+реп @user</code>!</i>")

    lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    lines.append("💡 <i>Оставить отзыв:</i> <code>+реп @user [причина]</code>")
    await message.reply("\n".join(lines), disable_web_page_preview=True)
