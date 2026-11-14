"""🎨 Модуль тем и глобального оформления чата MOXXI 3.0 REVOLUTION.

Предоставляет:
- 15 эксклюзивных кастомных тем с индивидуальными баннерами, рамками, иконками и разделителями;
- Строгую изоляцию настроек для каждого чата (смена темы в Чат 1 НИКОГДА не затронет Чат 2);
- Универсальные функции стилизации сообщений для всех модулей бота.
"""
from __future__ import annotations

import time
from typing import Any
import db

ALL_THEMES: dict[str, dict[str, Any]] = {
    "rainbow": {
        "id": "rainbow",
        "name": "🌈 Радужный Неон (Diamond Rainbow)",
        "badge": "🌈",
        "desc": "Фирменный градиентный стиль с кристаллами, алмазами и цветными акцентами",
        "banner": "✦ ══ • ⊰ 💖 🔮 💙 🩵 💚 💛 🟣 🧡 ❤️ 🤍 ⊱ • ══ ✦",
        "header_title": "👑 ✨ <b>{title}</b> ✨ 👑",
        "divider": "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
        "group_box": "┌ <b>{head}</b>",
        "branch_mid": "├─▸",
        "branch_last": "└─▸",
        "footer_banner": "✦ ══════════════════════════════ ✦",
        "footer_fmt": "📊 <i>Всего в администрации: <b>{total}</b></i>",
        "accent_icon": "💎",
        "bullets": {10: "👑", 9: "🔱", 8: "🔮", 7: "💎", 6: "⭐", 5: "🛡️", 4: "⚔️", 3: "🗡️", 2: "🔹", 1: "▫️"}
    },
    "cyber_sakura": {
        "id": "cyber_sakura",
        "name": "🌸 Сакура & Киберпанк (Tokyo Neo-Samurai)",
        "badge": "🌸",
        "desc": "Японский кибер-стиль с цветущей сакурой, неоновыми разделителями и катанами",
        "banner": "🌸 ════════ • ⛩️ • ════════ 🌸",
        "header_title": "🏮 🌸 <b>{title}</b> 🌸 🏮",
        "divider": "🌸 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🌸",
        "group_box": "┏━ 🌸 <b>{head}</b>",
        "branch_mid": "┣━▸",
        "branch_last": "┗━▸",
        "footer_banner": "🌸 ════════ • ⛩️ • ════════ 🌸",
        "footer_fmt": "⛩️ <i>Мастеров самурайского совета: <b>{total}</b></i>",
        "accent_icon": "🌸",
        "bullets": {10: "⛩️", 9: "🏮", 8: "⚡", 7: "🥷", 6: "🗡️", 5: "⚔️", 4: "🎋", 3: "🌸", 2: "🏮", 1: "🥋"}
    },
    "gold_luxury": {
        "id": "gold_luxury",
        "name": "👑 Королевское Золото (Imperial Gold)",
        "badge": "👑",
        "desc": "Роскошный императорский стиль с коронами, вензелями и золотыми слитками",
        "banner": "⚜️ ═══ ⋆ ★ ⋆ ═══ 👑 ═══ ⋆ ★ ⋆ ═══ ⚜️",
        "header_title": "👑 ⚜️ <b>{title}</b> ⚜️ 👑",
        "divider": "⚜️ ━━━━━━━━━━━━━━━━━━━━ ⚜️",
        "group_box": "╔══ 👑 <b>{head}</b>",
        "branch_mid": "╠══▸",
        "branch_last": "╚══▸",
        "footer_banner": "⚜️ ═══ ⋆ ★ ⋆ ═══ 👑 ═══ ⋆ ★ ⋆ ═══ ⚜️",
        "footer_fmt": "👑 <i>Императорский совет: <b>{total}</b></i>",
        "accent_icon": "👑",
        "bullets": {10: "👑", 9: "🔱", 8: "⚜️", 7: "💎", 6: "🪙", 5: "🛡️", 4: "⚔️", 3: "🗡️", 2: "🔸", 1: "▫️"}
    },
    "emerald_matrix": {
        "id": "emerald_matrix",
        "name": "🟢 Изумрудная Матрица (Cyber Matrix)",
        "badge": "🟢",
        "desc": "Неоновый зелёный терминал киберпространства и цифровых кристаллов",
        "banner": "⚡ ════════ • 🟢 • ════════ ⚡",
        "header_title": "💻 🟢 <b>{title}</b> 🟢 💻",
        "divider": "🟢 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🟢",
        "group_box": "┌── 🟢 <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "⚡ ════════ • 🟢 • ════════ ⚡",
        "footer_fmt": "💻 <i>Активных узлов терминала: <b>{total}</b></i>",
        "accent_icon": "🟢",
        "bullets": {10: "🟩", 9: "🟢", 8: "⚡", 7: "🔋", 6: "📟", 5: "💻", 4: "💾", 3: "🕹️", 2: "🔹", 1: "▫️"}
    },
    "neon_tokyo": {
        "id": "neon_tokyo",
        "name": "🏮 Неоновый Токио (Night Shibuya)",
        "badge": "🏮",
        "desc": "Атмосфера ночного Сибуя: неоновые вывески, фонари и дождь мегаполиса",
        "banner": "🏮 ═ ═ ═ • 🌆 • ═ ═ ═ 🏮",
        "header_title": "🏮 🌆 <b>{title}</b> 🌆 🏮",
        "divider": "🏮 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🏮",
        "group_box": "┏━ 🏮 <b>{head}</b>",
        "branch_mid": "┣━▸",
        "branch_last": "┗━▸",
        "footer_banner": "🏮 ═ ═ ═ • 🌆 • ═ ═ ═ 🏮",
        "footer_fmt": "🌆 <i>Синдикат Токио: <b>{total}</b></i>",
        "accent_icon": "🏮",
        "bullets": {10: "🏮", 9: "⛩️", 8: "🌃", 7: "🌆", 6: "✨", 5: "🥷", 4: "🗡️", 3: "🎋", 2: "🔹", 1: "▫️"}
    },
    "crimson_blood": {
        "id": "crimson_blood",
        "name": "🩸 Кровавый Закат (Vampire Crimson)",
        "badge": "🩸",
        "desc": "Тёмный вампирский стиль с рубинами, алой кровью и готическими шипами",
        "banner": "🩸 ━━━━━━━━ • 🍷 • ━━━━━━━━ 🩸",
        "header_title": "🍷 🩸 <b>{title}</b> 🩸 🍷",
        "divider": "🩸 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🩸",
        "group_box": "╔══ 🩸 <b>{head}</b>",
        "branch_mid": "╠══▸",
        "branch_last": "╚══▸",
        "footer_banner": "🩸 ━━━━━━━━ • 🍷 • ━━━━━━━━ 🩸",
        "footer_fmt": "🍷 <i>Ковен высшей крови: <b>{total}</b></i>",
        "accent_icon": "🩸",
        "bullets": {10: "🍷", 9: "🩸", 8: "🥀", 7: "🦇", 6: "🗡️", 5: "⚔️", 4: "🏹", 3: "🕯️", 2: "🔻", 1: "▫️"}
    },
    "deep_ocean": {
        "id": "deep_ocean",
        "name": "🌊 Глубокий Океан (Abyssal Poseidon)",
        "badge": "🌊",
        "desc": "Глубины морского царства с трезубцами Посейдона, жемчугом и волнами",
        "banner": "🌊 ════════ • 🔱 • ════════ 🌊",
        "header_title": "🌊 🔱 <b>{title}</b> 🔱 🌊",
        "divider": "🌊 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🌊",
        "group_box": "┌── 🌊 <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "🌊 ════════ • 🔱 • ════════ 🌊",
        "footer_fmt": "🔱 <i>Владык океанских глубин: <b>{total}</b></i>",
        "accent_icon": "🌊",
        "bullets": {10: "🔱", 9: "🌊", 8: "🐬", 7: "🫧", 6: "🐚", 5: "🪸", 4: "⚓", 3: "🧭", 2: "🔹", 1: "▫️"}
    },
    "amethyst_void": {
        "id": "amethyst_void",
        "name": "🔮 Аметистовая Бездна (Void Sorcery)",
        "badge": "🔮",
        "desc": "Мистический фиолетовый эфир древней магии, рун и тайных ритуалов",
        "banner": "🔮 ══ • ⊰ 🌌 👁️ 🌌 ⊱ • ══ 🔮",
        "header_title": "🔮 🌌 <b>{title}</b> 🌌 🔮",
        "divider": "🔮 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🔮",
        "group_box": "┏━ 🔮 <b>{head}</b>",
        "branch_mid": "┣━▸",
        "branch_last": "┗━▸",
        "footer_banner": "🔮 ══ • ⊰ 🌌 👁️ 🌌 ⊱ • ══ 🔮",
        "footer_fmt": "🔮 <i>Верховный совет магов: <b>{total}</b></i>",
        "accent_icon": "🔮",
        "bullets": {10: "🔮", 9: "🌌", 8: "👁️", 7: "✨", 6: "📜", 5: "🕯️", 4: "🗝️", 3: "🌙", 2: "🟣", 1: "▫️"}
    },
    "solar_flare": {
        "id": "solar_flare",
        "name": "☀️ Солнечная Вспышка (Solar Phoenix)",
        "badge": "☀️",
        "desc": "Ослепительное пламя феникса, солнечные протуберанцы и золотой жар",
        "banner": "☀️ ═══ • 🔥 ✧ 🔥 • ═══ ☀️",
        "header_title": "🔥 ☀️ <b>{title}</b> ☀️ 🔥",
        "divider": "🔥 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🔥",
        "group_box": "┌── 🔥 <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "☀️ ═══ • 🔥 ✧ 🔥 • ═══ ☀️",
        "footer_fmt": "☀️ <i>Хранителей священного огня: <b>{total}</b></i>",
        "accent_icon": "🔥",
        "bullets": {10: "☀️", 9: "🔥", 8: "💥", 7: "⚡", 6: "🌟", 5: "🛡️", 4: "⚔️", 3: "🗡️", 2: "🔸", 1: "▫️"}
    },
    "arctic_frost": {
        "id": "arctic_frost",
        "name": "❄️ Арктический Лёд (Glacial Frost)",
        "badge": "❄️",
        "desc": "Кристально чистый морозный лёд, снежные бури и северное сияние",
        "banner": "❄️ ════════ • 🧊 • ════════ ❄️",
        "header_title": "❄️ 🧊 <b>{title}</b> 🧊 ❄️",
        "divider": "❄️ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ ❄️",
        "group_box": "┌── ❄️ <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "❄️ ════════ • 🧊 • ════════ ❄️",
        "footer_fmt": "❄️ <i>Стражей ледяного трона: <b>{total}</b></i>",
        "accent_icon": "❄️",
        "bullets": {10: "🧊", 9: "❄️", 8: "💎", 7: "🏔️", 6: "🌬️", 5: "🛡️", 4: "⚔️", 3: "🗡️", 2: "🔹", 1: "▫️"}
    },
    "space_nebula": {
        "id": "space_nebula",
        "name": "🌌 Космическая Туманность (Cosmic Starfleet)",
        "badge": "🌌",
        "desc": "Глубокий космический вайб со звёздами, кометами, орбитами и туманностями",
        "banner": "✨ ⋆ ★ ━━━━━━━ • 🛸 • ━━━━━━━ ★ ⋆ ✨",
        "header_title": "🪐 🚀 <b>{title}</b> 🚀 🪐",
        "divider": "✨ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ ✨",
        "group_box": "┏━ 🪐 <b>{head}</b>",
        "branch_mid": "┣━💫",
        "branch_last": "┗━💫",
        "footer_banner": "✨ ⋆ ★ ━━━━━━━ • 🛸 • ━━━━━━━ ★ ⋆ ✨",
        "footer_fmt": "🛰️ <i>Экипаж командного мостика: <b>{total}</b></i>",
        "accent_icon": "🪐",
        "bullets": {10: "🪐", 9: "🚀", 8: "🛸", 7: "🌟", 6: "🌠", 5: "☄️", 4: "🛰️", 3: "💫", 2: "✨", 1: "🔭"}
    },
    "retrowave_synth": {
        "id": "retrowave_synth",
        "name": "🌴 Ретровейв 80-х (Miami Synthwave)",
        "badge": "🌴",
        "desc": "Неоновые закаты Майами, кассеты, спорткары и лазерная сетка 80-х",
        "banner": "🌴 ═══ 🌅 ═══ 📼 ═══ 🌅 ═══ 🌴",
        "header_title": "🌴 🌅 <b>{title}</b> 🌅 🌴",
        "divider": "🌅 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🌅",
        "group_box": "┌── 🌴 <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "🌴 ═══ 🌅 ═══ 📼 ═══ 🌅 ═══ 🌴",
        "footer_fmt": "📼 <i>Синтвейв-легенд клуба: <b>{total}</b></i>",
        "accent_icon": "🌴",
        "bullets": {10: "🌅", 9: "🌴", 8: "📼", 7: "🕶️", 6: "🏎️", 5: "🕹️", 4: "🎆", 3: "✨", 2: "🟣", 1: "▫️"}
    },
    "samurai_shadow": {
        "id": "samurai_shadow",
        "name": "🗡️ Тень Самурая (Shadow Ronin)",
        "badge": "🗡️",
        "desc": "Чёрно-серебряный монохром, клинки ниндзя, звёзды сюрикенов и лунный свет",
        "banner": "🗡️ ━━━━━━━━ • 🥷 • ━━━━━━━━ 🗡️",
        "header_title": "🥷 🗡️ <b>{title}</b> 🗡️ 🥷",
        "divider": "🗡️ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 🗡️",
        "group_box": "╔══ 🗡️ <b>{head}</b>",
        "branch_mid": "╠══▸",
        "branch_last": "╚══▸",
        "footer_banner": "🗡️ ━━━━━━━━ • 🥷 • ━━━━━━━━ 🗡️",
        "footer_fmt": "🥷 <i>Мастеров теневого клана: <b>{total}</b></i>",
        "accent_icon": "🗡️",
        "bullets": {10: "🥷", 9: "🗡️", 8: "⚔️", 7: "🎋", 6: "🌙", 5: "🛡️", 4: "🏹", 3: "⚖️", 2: "🔹", 1: "▫️"}
    },
    "cyber_diamond": {
        "id": "cyber_diamond",
        "name": "💎 Кибер-Алмаз (Diamond Elite VIP)",
        "badge": "💎",
        "desc": "Эксклюзивная кристалльная тема VIP-клуба с сияющими бриллиантами",
        "banner": "💎 ════════ • 💠 • ════════ 💎",
        "header_title": "💎 💠 <b>{title}</b> 💠 💎",
        "divider": "💎 ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ 💎",
        "group_box": "┌── 💎 <b>{head}</b>",
        "branch_mid": "├──▸",
        "branch_last": "└──▸",
        "footer_banner": "💎 ════════ • 💠 • ════════ 💎",
        "footer_fmt": "💎 <i>Элитных участников VIP: <b>{total}</b></i>",
        "accent_icon": "💎",
        "bullets": {10: "💎", 9: "💠", 8: "🔷", 7: "✨", 6: "⭐", 5: "🛡️", 4: "⚔️", 3: "🗡️", 2: "🔹", 1: "▫️"}
    },
    "royal_infinity": {
        "id": "royal_infinity",
        "name": "🪐 Королевская Бесконечность (VIP+ Diamond Infinity)",
        "badge": "🪐",
        "desc": "Ультимативная космическая привилегия VIP+ с золотым сиянием бесконечности",
        "banner": "🪐 ═ ⋆ ⚜️ ⋆ ═ 👑 ═ ⋆ ⚜️ ⋆ ═ 🪐",
        "header_title": "🪐 👑 <b>{title}</b> 👑 🪐",
        "divider": "🪐 ━━━━━━━━━━━━━━━━━━━━ 🪐",
        "group_box": "╔══ 🪐 <b>{head}</b>",
        "branch_mid": "╠══💫",
        "branch_last": "╚══💫",
        "footer_banner": "🪐 ═ ⋆ ⚜️ ⋆ ═ 👑 ═ ⋆ ⚜️ ⋆ ═ 🪐",
        "footer_fmt": "🪐 <i>Императоров бесконечности VIP+: <b>{total}</b></i>",
        "accent_icon": "🪐",
        "bullets": {10: "🪐", 9: "👑", 8: "⚜️", 7: "💎", 6: "🌟", 5: "✨", 4: "💫", 3: "🔮", 2: "🔸", 1: "▫️"}
    }
}


async def get_chat_theme(chat_id: int) -> dict[str, Any]:
    """Получает тему оформления строго для указанного чата (полная изоляция)."""
    try:
        row = await db.fetchone("SELECT theme FROM chat_themes WHERE chat_id=?", (chat_id,))
        if row and row.get("theme") in ALL_THEMES:
            return ALL_THEMES[row["theme"]]
    except Exception:
        pass
    return ALL_THEMES["rainbow"]


async def set_chat_theme(chat_id: int, theme_id: str, updated_by: int = 0) -> bool:
    """Устанавливает тему строго для указанного чата. Другие чаты не затрагиваются!"""
    if theme_id not in ALL_THEMES:
        return False
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_themes ("
        "chat_id INTEGER PRIMARY KEY, "
        "theme TEXT NOT NULL DEFAULT 'rainbow', "
        "hierarchy TEXT NOT NULL DEFAULT 'default', "
        "gender_mode TEXT NOT NULL DEFAULT 'auto', "
        "updated_at INTEGER NOT NULL DEFAULT 0, "
        "updated_by INTEGER NOT NULL DEFAULT 0)"
    )
    now = int(time.time())
    await db.execute(
        "INSERT INTO chat_themes (chat_id, theme, updated_at, updated_by) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET theme=excluded.theme, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (chat_id, theme_id, now, updated_by)
    )
    return True


async def format_header(chat_id: int, title: str) -> str:
    """Форматирует красивый верхний заголовок с баннером чата."""
    t = await get_chat_theme(chat_id)
    banner = t["banner"]
    header = t["header_title"].format(title=title)
    return f"{banner}\n{header}\n{banner}"


async def format_divider(chat_id: int) -> str:
    """Возвращает разделитель в стиле темы текущего чата."""
    t = await get_chat_theme(chat_id)
    return t.get("divider", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")


async def format_footer(chat_id: int, total: int = 0) -> str:
    """Возвращает нижний баннер в стиле темы текущего чата."""
    t = await get_chat_theme(chat_id)
    banner = t["footer_banner"]
    fmt = t["footer_fmt"].format(total=total)
    return f"{banner}\n{fmt}"
