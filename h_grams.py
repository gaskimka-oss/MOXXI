"""Монеты-бот: игровая валюта «монеты» 🪙, предприятия, динамический рынок и игры.

Игры: слоты/казино, орёл/решка, мины, дартс, краш, колесо, сапёр (на двоих), кубик, рулетка.
Бизнесы и недвижимость: фермы, аренда домов, заводы, ТЦ, шахты, электростанции, вышки, космодромы.
Динамический рынок: цены колеблются каждый час в зависимости от спроса.
Игровой уровень: прокачка за игры в казино и открытие новых бизнесов.
"""
from __future__ import annotations

import asyncio
import html
import random
import time

from aiogram import Bot, F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

import db
import core_backup
from core_registry import Cmd
from core_resolve import human_period, parse_period, resolve_target
from utils import hms, mention, mention_id, parse_amount, money, make_game_replay_kb

router = Router(name="grams")
S = 33  # раздел «Монеты, бизнесы и игры»

COIN = "🪙"
COINS = COIN
COMET = COIN
GRAM = COIN  # алиас для совместимости
MIN_BET = 100
MAX_BET = 50_000_000
DAILY_COINS = 2_500
DAILY_COMETS = DAILY_COINS
DAILY_GRAMS = DAILY_COINS
DAILY_CD = 4 * 3600
START_COINS = 1_000
START_COMETS = START_COINS
START_GRAMS = START_COINS


def c(n: int) -> str:
    """Форматирование: 1 500 000 → 1 500 000 🪙"""
    return f"{n:,}".replace(",", " ") + f" {COIN}"


g = c  # алиас для совместимости


# ═══════════════ СПИСОК ПРЕДПРИЯТИЙ И НЕДВИЖИМОСТИ (30 ОБЪЕКТОВ ДО 100 LVL) ═══════════════
BUSINESS_TYPES: dict[str, dict] = {
    "farm": {
        "id": 1,
        "name": "Ферма",
        "emoji": "🌾",
        "base_price": 5_000,
        "income_per_min": 15,
        "req_lvl": 1,
        "desc": "Выращивание урожая и органических культур",
        "aliases": ["ферма", "ферму", "фермы", "farm", "1"]
    },
    "house": {
        "id": 2,
        "name": "Дом в аренду",
        "emoji": "🏠",
        "base_price": 18_000,
        "income_per_min": 55,
        "req_lvl": 2,
        "desc": "Сдача коттеджа жильцам",
        "aliases": ["дом", "дом в аренду", "коттедж", "аренда", "house", "2"]
    },
    "factory": {
        "id": 3,
        "name": "Завод",
        "emoji": "🏭",
        "base_price": 60_000,
        "income_per_min": 200,
        "req_lvl": 3,
        "desc": "Производство электроники и потребительских товаров",
        "aliases": ["завод", "заводы", "фабрика", "factory", "3"]
    },
    "mall": {
        "id": 4,
        "name": "Торговый центр",
        "emoji": "🏢",
        "base_price": 200_000,
        "income_per_min": 750,
        "req_lvl": 4,
        "desc": "Аренда бутиков, фудкортов и гипермаркетов",
        "aliases": ["тц", "торговый центр", "бизнес-центр", "бц", "mall", "4"]
    },
    "mine": {
        "id": 5,
        "name": "Крипто-шахта",
        "emoji": "⛏",
        "base_price": 712_500,
        "income_per_min": 3_000,
        "req_lvl": 5,
        "desc": "Добыча редких кристаллов и крипто-руды",
        "aliases": ["шахта", "шахту", "крипто-шахта", "криптошахта", "mine", "5"]
    },
    "power": {
        "id": 6,
        "name": "Электростанция",
        "emoji": "⚡",
        "base_price": 2_500_000,
        "income_per_min": 11_000,
        "req_lvl": 6,
        "desc": "Генерация энергии для крупнейших мегаполисов",
        "aliases": ["станция", "электростанция", "аэс", "гэс", "power", "6"]
    },
    "rig": {
        "id": 7,
        "name": "Нефтяная вышка",
        "emoji": "🛢",
        "base_price": 8_000_000,
        "income_per_min": 38_000,
        "req_lvl": 8,
        "desc": "Добыча и переработка чёрного золота",
        "aliases": ["вышка", "вышку", "нефтяная вышка", "нефть", "rig", "7"]
    },
    "space": {
        "id": 8,
        "name": "Космодром",
        "emoji": "🚀",
        "base_price": 30_000_000,
        "income_per_min": 160_000,
        "req_lvl": 10,
        "desc": "Запуск коммерческих шаттлов и научных ракет",
        "aliases": ["космодром", "ракета", "space", "8"]
    },
    "bank": {
        "id": 9,
        "name": "Банковский конгломерат",
        "emoji": "🏦",
        "base_price": 85_000_000,
        "income_per_min": 480_000,
        "req_lvl": 12,
        "desc": "Управление международными финансовыми потоками",
        "aliases": ["банк", "банки", "конгломерат", "банковский конгломерат", "bank", "9"]
    },
    "orbital": {
        "id": 10,
        "name": "Орбитальная станция",
        "emoji": "🛰",
        "base_price": 220_000_000,
        "income_per_min": 1_300_000,
        "req_lvl": 15,
        "desc": "Космические исследования и верфи на околоземной орбите",
        "aliases": ["орбиталка", "орбитальная станция", "orbital", "10"]
    },
    "megacorp": {
        "id": 11,
        "name": "Межгалактическая корпорация",
        "emoji": "💎",
        "base_price": 500_000_000,
        "income_per_min": 3_200_000,
        "req_lvl": 18,
        "desc": "Владение торговыми путями через дальние звёздные сектора",
        "aliases": ["корпорация", "межгалактическая корпорация", "мегакорп", "megacorp", "11"]
    },
    "dyson": {
        "id": 12,
        "name": "Сфера Дайсона",
        "emoji": "🌌",
        "base_price": 1_200_000_000,
        "income_per_min": 8_500_000,
        "req_lvl": 22,
        "desc": "Мегаструктура вокруг звезды для колоссальной выработки энергии",
        "aliases": ["сфера дайсона", "дайсон", "сфера", "12"]
    },
    "mars_colony": {
        "id": 13,
        "name": "Колония на Марсе",
        "emoji": "🪐",
        "base_price": 2_800_000_000,
        "income_per_min": 21_000_000,
        "req_lvl": 26,
        "desc": "Терраформирование красной планеты и биокупола",
        "aliases": ["марс", "колония на марсе", "колония", "mars", "13"]
    },
    "collider": {
        "id": 14,
        "name": "Термоядерный коллайдер",
        "emoji": "⚛️",
        "base_price": 6_500_000_000,
        "income_per_min": 52_000_000,
        "req_lvl": 30,
        "desc": "Синтез редчайших античастиц и бозонов массы",
        "aliases": ["коллайдер", "термояд", "синтез", "collider", "14"]
    },
    "quantum_lab": {
        "id": 15,
        "name": "Квантовый биокомплекс",
        "emoji": "🧬",
        "base_price": 15_000_000_000,
        "income_per_min": 130_000_000,
        "req_lvl": 35,
        "desc": "Регенерация ДНК и квантовые нейрочипы",
        "aliases": ["квант", "биокомплекс", "квантовый биокомплекс", "15"]
    },
    "star_fleet": {
        "id": 16,
        "name": "Флот Звёздных Разрушителей",
        "emoji": "🛸",
        "base_price": 35_000_000_000,
        "income_per_min": 320_000_000,
        "req_lvl": 40,
        "desc": "Космическая армада для защиты торговых гипер-маршрутов",
        "aliases": ["флот", "разрушители", "армада", "звездный флот", "16"]
    },
    "stargate": {
        "id": 17,
        "name": "Звёздные врата Варпа",
        "emoji": "🌠",
        "base_price": 80_000_000_000,
        "income_per_min": 780_000_000,
        "req_lvl": 45,
        "desc": "Мгновенные гиперпространственные прыжки через парсеки",
        "aliases": ["врата", "варп", "звездные врата", "stargate", "17"]
    },
    "black_hole": {
        "id": 18,
        "name": "Генератор Чёрных Дыр",
        "emoji": "🌀",
        "base_price": 190_000_000_000,
        "income_per_min": 1_950_000_000,
        "req_lvl": 50,
        "desc": "Добыча гравитационной энергии из горизонта событий",
        "aliases": ["черная дыра", "генератор черных дыр", "гравитация", "18"]
    },
    "chrono_lab": {
        "id": 19,
        "name": "Хроно-лаборатория времени",
        "emoji": "🔮",
        "base_price": 450_000_000_000,
        "income_per_min": 4_800_000_000,
        "req_lvl": 55,
        "desc": "Манипуляции с квантовым потоком времени",
        "aliases": ["хроно", "время", "хроно-лаборатория", "chrono", "19"]
    },
    "dark_matter": {
        "id": 20,
        "name": "Фабрика Тёмной материи",
        "emoji": "💫",
        "base_price": 1_000_000_000_000,
        "income_per_min": 11_500_000_000,
        "req_lvl": 60,
        "desc": "Конденсация тёмной материи для двигателей судного дня",
        "aliases": ["темная материя", "фабрика темной материи", "материя", "20"]
    },
    "alliance": {
        "id": 21,
        "name": "Галактический Альянс",
        "emoji": "🌌",
        "base_price": 2_500_000_000_000,
        "income_per_min": 30_000_000_000,
        "req_lvl": 65,
        "desc": "Политический и торговый союз тысяч звёздных цивилизаций",
        "aliases": ["альянс", "галактический альянс", "союз", "21"]
    },
    "quasar": {
        "id": 22,
        "name": "Звёздный кузнец квазаров",
        "emoji": "☀️",
        "base_price": 6_000_000_000_000,
        "income_per_min": 75_000_000_000,
        "req_lvl": 70,
        "desc": "Ковка звёздных ядер на ревущей мощи квазаров",
        "aliases": ["квазар", "кузнец", "кузнец квазаров", "22"]
    },
    "singularity": {
        "id": 23,
        "name": "Энергостанция Сингулярности",
        "emoji": "🕳",
        "base_price": 15_000_000_000_000,
        "income_per_min": 190_000_000_000,
        "req_lvl": 75,
        "desc": "Абсолютная точка сжатия пространства и бесконечной тяги",
        "aliases": ["сингулярность", "станция сингулярности", "23"]
    },
    "ring_worlds": {
        "id": 24,
        "name": "Мегаструктура «Кольцо Миров»",
        "emoji": "🪐",
        "base_price": 38_000_000_000_000,
        "income_per_min": 500_000_000_000,
        "req_lvl": 80,
        "desc": "Обитаемый монолитный пояс радиусом в миллионы километров",
        "aliases": ["кольцо миров", "кольцо", "мегаструктура", "24"]
    },
    "mind_matrix": {
        "id": 25,
        "name": "Матрица Перерождения Разума",
        "emoji": "🧬",
        "base_price": 95_000_000_000_000,
        "income_per_min": 1_300_000_000_000,
        "req_lvl": 85,
        "desc": "Цифровое бессмертие и единое суперсознание вселенной",
        "aliases": ["матрица", "разум", "матрица разума", "25"]
    },
    "supercluster": {
        "id": 26,
        "name": "Сверхскопление Мета-Вселенной",
        "emoji": "🌌",
        "base_price": 240_000_000_000_000,
        "income_per_min": 3_400_000_000_000,
        "req_lvl": 90,
        "desc": "Полный контроль над миллионами взаимосвязанных галактик",
        "aliases": ["сверхскопление", "метавселенная", "мета", "26"]
    },
    "void_throne": {
        "id": 27,
        "name": "Трон Властелина Пространства",
        "emoji": "👑",
        "base_price": 600_000_000_000_000,
        "income_per_min": 9_000_000_000_000,
        "req_lvl": 93,
        "desc": "Центр управления законами физики и геометрии космоса",
        "aliases": ["трон", "властелин", "трон пространства", "27"]
    },
    "multiverse_core": {
        "id": 28,
        "name": "Ядро Мультивселенной",
        "emoji": "♾",
        "base_price": 1_500_000_000_000_000,
        "income_per_min": 24_000_000_000_000,
        "req_lvl": 96,
        "desc": "Слияние параллельных измерений в единый поток ресурсов",
        "aliases": ["ядро", "мультивселенная", "ядро мультивселенной", "28"]
    },
    "reality_forge": {
        "id": 29,
        "name": "Творец Реальностей",
        "emoji": "🌠",
        "base_price": 4_000_000_000_000_000,
        "income_per_min": 68_000_000_000_000,
        "req_lvl": 98,
        "desc": "Создание и уничтожение новых вселенных по щелчку пальцев",
        "aliases": ["творец", "реальность", "творец реальностей", "29"]
    },
    "omniverse": {
        "id": 30,
        "name": "Омниверсум Создателя",
        "emoji": "👑",
        "base_price": 10_000_000_000_000_000,
        "income_per_min": 180_000_000_000_000,
        "req_lvl": 100,
        "desc": "Абсолютная вершина мироздания и вечной власти",
        "aliases": ["омниверсум", "создатель", "абсолют", "30"]
    },
    # Обратная совместимость для ранее купленных ключей:
    "cafe": {"id": 1, "name": "Кофейня", "emoji": "☕️", "base_price": 10_000, "income_per_min": 32, "req_lvl": 1, "desc": "Кофейня", "aliases": ["кофейня", "кафе"]},
    "autoservice": {"id": 2, "name": "Автосервис", "emoji": "🚗", "base_price": 35_000, "income_per_min": 115, "req_lvl": 2, "desc": "Автосервис", "aliases": ["автосервис"]},
    "pizzeria": {"id": 3, "name": "Пиццерия", "emoji": "🍕", "base_price": 110_000, "income_per_min": 390, "req_lvl": 3, "desc": "Пиццерия", "aliases": ["пиццерия"]},
    "port": {"id": 4, "name": "Порт", "emoji": "🚢", "base_price": 420_000, "income_per_min": 1_650, "req_lvl": 4, "desc": "Порт", "aliases": ["порт"]},
    "skyscraper": {"id": 5, "name": "Небоскрёб", "emoji": "🏙", "base_price": 1_400_000, "income_per_min": 6_000, "req_lvl": 5, "desc": "Небоскрёб", "aliases": ["небоскреб"]},
    "airline": {"id": 6, "name": "Авиакомпания", "emoji": "✈️", "base_price": 4_800_000, "income_per_min": 22_000, "req_lvl": 7, "desc": "Авиакомпания", "aliases": ["авиа"]},
    "biolab": {"id": 7, "name": "Биолаборатория", "emoji": "🧬", "base_price": 16_000_000, "income_per_min": 82_000, "req_lvl": 9, "desc": "Биолаборатория", "aliases": ["биолаборатория"]},
    "starlink": {"id": 8, "name": "Спутниковая сеть", "emoji": "🛰", "base_price": 52_000_000, "income_per_min": 285_000, "req_lvl": 11, "desc": "Спутники", "aliases": ["старлинк"]},
    "moon": {"id": 9, "name": "Лунная база", "emoji": "🪐", "base_price": 140_000_000, "income_per_min": 810_000, "req_lvl": 13, "desc": "Лунная база", "aliases": ["луна"]},
    "asteroid": {"id": 10, "name": "Астероидный рудник", "emoji": "☄️", "base_price": 340_000_000, "income_per_min": 2_100_000, "req_lvl": 16, "desc": "Рудник", "aliases": ["астероид"]},
}


def get_market_multiplier(biz_key: str) -> float:
    """Динамический множитель рынка (меняется каждый час, от 0.80 до 1.30)."""
    hour_seed = int(time.time() // 3600)
    # Псевдослучайный хэш для стабильности в течение часа
    h = (abs(hash(f"{biz_key}:{hour_seed}")) % 1000)
    return round(0.80 + (h / 1000.0) * 0.50, 2)


def get_market_price(biz_key: str, is_sell: bool = False) -> tuple[int, str]:
    """Возвращает (цена_акции, тренд_строка)."""
    info = BUSINESS_TYPES.get(biz_key)
    if not info:
        return 0, "➡️ 0%"
    mult = get_market_multiplier(biz_key)
    base = info["base_price"]
    if is_sell:
        price = max(1, int(base * 0.50 * mult))  # Срочная ликвидация б/у (уценка ~50%)
    else:
        price = max(1, int(base * mult))

    diff_pct = int(round((mult - 1.0) * 100))
    if diff_pct > 5:
        trend = f"📈 +{diff_pct}%"
    elif diff_pct < -5:
        trend = f"📉 {diff_pct}%"
    else:
        trend = f"➡️ ~0%"
    return price, trend


def find_business_by_alias(query: str) -> tuple[str | None, dict | None]:
    q = (query or "").strip().lower()
    for k, v in BUSINESS_TYPES.items():
        if q == k or q in v["aliases"] or q.startswith(v["name"].lower()):
            return k, v
    return None, None


async def _ensure_start(uid: int) -> None:
    """Первый вход — выдаём стартовые монеты."""
    u = await db.get_user(uid)
    if u["grams"] == 0:
        row = await db.fetchone(
            "SELECT 1 FROM log WHERE user_id=? AND action='gram_start'", (uid,))
        if not row:
            await db.add_coins(uid, START_COINS, "gram_start")


async def get_gram_topic(chat_id: int) -> int:
    from core_seed import MAIN_CHAT
    default_val = "132681" if (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")) else "0"
    v = await db.get_setting(chat_id, "gram_topic", default_val)
    try:
        val = int(v)
        if val == 0 and (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")):
            return 132681
        return val
    except ValueError:
        return 132681 if (chat_id == MAIN_CHAT or str(chat_id).endswith("3934033202")) else 0


def _tid(message: Message) -> int:
    return int(getattr(message, "message_thread_id", None) or 0)


def _tlink(chat_id: int, tid: int) -> str:
    cid = str(chat_id)
    short = cid[4:] if cid.startswith("-100") else cid.lstrip("-")
    return f"https://t.me/c/{short}/{tid}"


async def casino_enabled(chat_id: int) -> bool:
    """Включено ли казино и игры в этом чате (по умолчанию '1')."""
    return await db.get_setting(chat_id, "casino_enabled", "1") == "1"


async def topic_ok(message: Message) -> bool:
    """Проверяет тему для игр, казино, заработка, ограблений и монет."""
    if message.chat.type != "private":
        if not await casino_enabled(message.chat.id):
            await message.reply(
                "🎰 <b>Казино и игры отключены в этом чате администрацией.</b>\n"
                "Включить: <code>+казино</code> (доступно администрации)",
                disable_web_page_preview=True
            )
            return False

        ft = await get_gram_topic(message.chat.id)
        if ft:
            tid = _tid(message)
            if tid != ft:
                chat_id = message.chat.id
                text = (
                    f"❌ {mention(message.from_user)}, здесь нельзя играть и совершать операции с валютой!\n\n"
                    f"🎰 <b>Игры, казино, работа, ограбления и монеты</b> — только в этой теме:\n"
                    f"{_tlink(chat_id, ft)}"
                )
                try:
                    await message.reply(text, disable_web_page_preview=True)
                except Exception:
                    pass
                return False
    return True


@router.message(Cmd("+казино", "+казик", "+игры", "вкл казино", "вкл казик", "вкл игры",
                    "-казино", "-казик", "-игры", "выкл казино", "выкл казик", "выкл игры",
                    "казино статус", "игры статус",
                    section=S, rank=3, group_only=True,
                    usage="+казино / -казино", desc="Включить/отключить казино и игры в чате"))
async def cmd_toggle_casino(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    cmd_word = (message.text or "").strip().lower()
    a = (args or "").strip().lower()

    if cmd_word.startswith(("-казино", "-казик", "-игры", "выкл казино", "выкл казик", "выкл игры")) or a in {"выкл", "off", "нет", "0", "disable"}:
        if not await require(message, bot, 3):
            return
        await db.set_setting(message.chat.id, "casino_enabled", "0")
        return await message.reply("🛑 <b>Казино и мини-игры в чате отключены!</b>\nВсе азартные команды заблокированы в этой беседе.")

    if cmd_word.startswith(("+казино", "+казик", "+игры", "вкл казино", "вкл казик", "вкл игры")) or a in {"вкл", "on", "да", "1", "enable"}:
        if not await require(message, bot, 3):
            return
        await db.set_setting(message.chat.id, "casino_enabled", "1")
        return await message.reply("✅ <b>Казино и мини-игры в чате включены!</b>\nИгрокам доступны слоты, мины, краш, дартс, рулетка и заработок.")

    cur = await casino_enabled(message.chat.id)
    status_str = "🟢 Включено" if cur else "⚪️ Отключено"
    await message.reply(
        f"🎰 <b>Игровая система (Казино и мини-игры)</b>\n\n"
        f"Текущий статус: <b>{status_str}</b>\n\n"
        f"• Включить: <code>+казино</code> или <code>вкл казик</code>\n"
        f"• Отключить: <code>-казино</code> или <code>выкл казик</code>\n"
        f"• Сыграть: <code>казик 100</code>"
    )


async def take_bet(message: Message, raw: str, **kw) -> int | None:
    """Проверяет ставку в монетах."""
    if not await topic_ok(message):
        return None
    uid = message.from_user.id
    await _ensure_start(uid)
    bal = await db.get_coins(uid)
    bet = parse_amount(raw, bal, MIN_BET)
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    if not bet or bet < MIN_BET:
        if not had_prefix and in_group:
            return None
        await message.reply(
            f"Минимальная ставка — <b>{c(MIN_BET)}</b>\n"
            f"Ваш баланс: <b>{c(bal)}</b>\n\n"
            f"Пример: <code>орёл 1000</code> · <code>мины 5к</code> · "
            f"<code>краш все</code>")
        return None
    if bet > MAX_BET:
        if not had_prefix and in_group:
            return None
        await message.reply(f"Максимальная ставка — <b>{c(MAX_BET)}</b>")
        return None
    if bet > bal:
        if not had_prefix and in_group:
            return None
        await message.reply(f"Недостаточно монет.\nВаш баланс: <b>{c(bal)}</b>")
        return None

    # Отчисление 2% в накопительный джекпот чата
    if message.chat.type in {"group", "supergroup"}:
        try:
            await db.add_to_chat_jackpot(message.chat.id, int(bet * 0.02))
        except Exception:
            pass

    return bet


# ═══════════════ БАЛАНС И СТАТИСТИКА ═══════════════
@router.message(Cmd("б", "баланс", "монеты", "коины", "граммы", "деньги", "мои монеты", "баланс монет", "мои коины", "мои граммы", "б монет", "coins", "grams", section=S,
                    usage="б", desc="Финансовый профиль и баланс"))
async def cmd_balance(message: Message, bot: Bot, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    if not had_prefix and in_group and (args or "").strip():
        from core_resolve import real_reply
        if not args.strip().startswith("@") and not args.strip().isdigit() and real_reply(message) is None:
            return

    uid, name, _ = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
    await _ensure_start(uid)

    bal = await db.get_balance(uid)

    # Игровой уровень и опыт
    prof = await db.get_game_profile(uid)
    lvl = prof["level"]
    xp = prof["xp"]
    next_xp = prof["next_xp"]
    pct = prof["progress_pct"]
    bar_len = 10
    filled = int((pct / 100) * bar_len)
    bar = "▰" * filled + "▱" * (bar_len - filled)

    # Бизнесы и пассивный доход
    user_biz = await db.get_user_businesses(uid)
    total_biz = sum(b["count"] for b in user_biz.values())
    income_min = sum(user_biz[k]["count"] * BUSINESS_TYPES[k]["income_per_min"] for k in user_biz if k in BUSINESS_TYPES)

    # Проверка защиты мешка
    hide_left = await db.cooldown_left(uid, "bag_hidden", 5 * 3600)
    bag_status = f"🛡 Защищён ({hms(hide_left)})" if hide_left else "🔓 Открыт для воров"

    # Бонус
    vip_lvl, _, vip_active = await db.get_vip_info(uid)
    cd = 3600 if (vip_active and vip_lvl >= 2) else (7200 if (vip_active and vip_lvl >= 1) else 14400)
    left_bonus = await db.cooldown_left(uid, "gram_daily", cd)
    if left_bonus:
        bonus_line = f"⏳ Бонус через: <b>{hms(left_bonus)}</b>"
    else:
        bonus_line = f"🎁 <b>Бонус готов!</b> Заберите <code>бонус</code>"

    txt = (
        f"💳 <b>ФИНАНСОВЫЙ ПРОФИЛЬ</b>\n"
        f"👤 {mention_id(uid, name)}\n\n"
        f"🪙 <b>Баланс Монет:</b> <code>{c(bal)}</code>\n\n"
        f"🎮 <b>Игровой уровень:</b> <b>{lvl} LVL</b> ({xp}/{next_xp} XP)\n"
        f"📊 Прогресс: <code>[{bar}]</code> {pct}%\n"
        f"🎲 Сыграно игр: <b>{prof['games_played']}</b> (побед: {prof['games_won']})\n\n"
        f"🏢 <b>Предприятия:</b> <b>{total_biz} шт.</b>\n"
        f"💵 Доход: <b>+{income_min:,} 🪙/мин</b>\n"
        f"🔒 Мешок: <b>{bag_status}</b>\n\n"
        f"{bonus_line}\n"
        f"💡 <i>Команды:</i> <code>бизнесы</code> · <code>игры</code> · <code>скрыть мешок</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏢 Мои бизнесы", callback_data="biz:menu"),
        InlineKeyboardButton(text="💰 Собрать прибыль", callback_data="biz:collect")
    ]])
    await message.reply(txt, reply_markup=kb)


@router.message(Cmd("бонус", "бонус монет", "бонус коинов", "бонус грамм", "монеты бонус", "ежедневный бонус", section=S,
                    usage="бонус", desc="Бонус от 1 до 30 000 монет"))
async def cmd_daily(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type in {"group", "supergroup"} and (args or "").strip():
        return
    uid = message.from_user.id
    await _ensure_start(uid)
    vip_lvl, _, vip_active = await db.get_vip_info(uid)
    cd = 3600 if (vip_active and vip_lvl >= 2) else (7200 if (vip_active and vip_lvl >= 1) else 14400)
    left = await db.cooldown_left(uid, "gram_daily", cd)
    if left:
        return await message.reply(
            f"⏳ Бонус уже получен.\n"
            f"Следующий через <b>{hms(left)}</b>\n\n"
            f"<i>💡 Кулдаун общий для всех чатов и личных сообщений бота.</i>"
        )
    # Сначала фиксируем кулдаун в БД для предотвращения одновременного сбора
    await db.set_cooldown(uid, "gram_daily")

    base_bonus = random.randint(1, 30_000)
    vip_mult = 2.0 if (vip_active and vip_lvl >= 2) else (1.5 if (vip_active and vip_lvl >= 1) else 1.0)
    final_bonus = int(base_bonus * vip_mult)

    bal = await db.add_balance(uid, final_bonus, "daily_bonus")

    vip_tag = ""
    if vip_active and vip_lvl >= 2:
        vip_tag = f"\n🌟 <i>VIP+ бонус x2 (+{final_bonus - base_bonus:,} 🪙)!</i>"
    elif vip_active and vip_lvl >= 1:
        vip_tag = f"\n⭐️ <i>VIP бонус +50% (+{final_bonus - base_bonus:,} 🪙)!</i>"

    await message.reply(
        f"🎁 <b>Ежедневный бонус!</b>\n\n"
        f"🎲 Выпало: <b>+{c(final_bonus)}</b> 🎉{vip_tag}\n"
        f"💰 Ваш баланс: <b>{c(bal)}</b>\n"
        f"⏳ Следующий бонус через <b>{hms(cd)}</b>"
    )


@router.message(Cmd("топ", "топ монет", "топ игроков", "топ коинов", "топ грамм", "топ граммов", "топ грами", "топ богатых", "топ баланс", "топ по монетам", "топ монет", section=S,
                    usage="топ", desc="Богатейшие игроки"))
async def cmd_top(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type in {"group", "supergroup"} and (args or "").strip():
        if (args or "").strip().lower() not in {"монет", "игроков", "коинов", "грамм", "граммов", "баланс", "богатых", "по монетам"}:
            return
    rows = await db.fetchall(
        "SELECT user_id, first_name, username, balance FROM users WHERE balance > 0 "
        "ORDER BY balance DESC LIMIT 10")
    if not rows:
        return await message.reply("Пока никто не играл.")
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    lines = []
    for i, r in enumerate(rows):
        uname = r["first_name"] or r["username"] or f"Игрок {r['user_id']}"
        lines.append(f"{medals[i]} {mention_id(r['user_id'], uname)} — {c(r['balance'])}")
    await message.reply(f"🪙 <b>Топ игроков по балансу</b>\n\n" + "\n".join(lines))


@router.message(Cmd("восстановить топ", "сброс топа", "сбросить топ", "вернуть топ", "фикс топа", "исправить топ",
                    "restore top", "reset top", section=S,
                    usage="восстановить топ", desc="Восстановить эталонный топ балансов и сбросить баганные триллионы"))
async def cmd_restore_top(message: Message, bot: Bot, **kw):
    import config
    from core_ranks import effective_rank
    have = await effective_rank(message, bot)
    is_admin = bool(message.from_user and (message.from_user.id == config.OWNER_ID or message.from_user.id in config.ADMINS or message.from_user.id in (8412527198, 8297844640, 6592023977)))
    if have < 6 and not is_admin:
        return await message.reply("🔒 Команда доступна техническому администратору и руководству.")
    
    res = await db.reset_all_businesses_and_levels()
    rows = await db.fetchall(
        "SELECT user_id, first_name, balance FROM users WHERE balance > 0 "
        "ORDER BY balance DESC LIMIT 10")
    
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    top_lines = "\n".join(
        f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — {c(r['balance'])}"
        for i, r in enumerate(rows))
    
    await message.reply(
        f"🏆 <b>Эталонный топ балансов успешно восстановлен!</b>\n\n"
        f"✅ Сброшены накрученные триллионы и баги\n"
        f"✅ Снесено накрученных предприятий: <b>{res['businesses_deleted']}</b> шт.\n"
        f"✅ Сброшены уровни казино у <b>{res['stats_reset']}</b> пользователей\n\n"
        f"🪙 <b>Актуальный топ по балансу:</b>\n{top_lines}")


@router.message(Cmd("снести фермы", "сброс ферм", "сбросить фермы", "снести бизнесы", "сброс бизнесов",
                    "сбросить бизнесы", "сброс экономики", "сбросить экономику", "снести все фермы",
                    "вайп ферм", "вайп бизнесов", "вайп экономики", "сброс уровней", "reset biz",
                    section=S,
                    usage="снести фермы", desc="Снести все купленные фермы/заводы, сбросить уровни и вернуть балансы"))
async def cmd_wipe_businesses(message: Message, bot: Bot, **kw):
    import config
    from core_ranks import effective_rank
    have = await effective_rank(message, bot)
    is_admin = bool(message.from_user and (message.from_user.id == config.OWNER_ID or message.from_user.id in config.ADMINS or message.from_user.id in (8412527198, 8297844640, 6592023977)))
    if have < 6 and not is_admin:
        return await message.reply("🔒 Команда доступна техническому администратору и руководству.")

    res = await db.reset_all_businesses_and_levels()
    rows = await db.fetchall(
        "SELECT user_id, first_name, balance FROM users WHERE balance > 0 "
        "ORDER BY balance DESC LIMIT 10")

    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    top_lines = "\n".join(
        f"{medals[i]} {mention_id(r['user_id'], r['first_name'])} — {c(r['balance'])}"
        for i, r in enumerate(rows))

    await message.reply(
        f"🧹 <b>Экономика и имущество полностью очищены!</b>\n\n"
        f"✅ <b>Снесено предприятий:</b> {res['businesses_deleted']} шт. (все фермы, заводы, дома, ТЦ, шахты удалены)\n"
        f"✅ <b>Сброшены уровни казино:</b> у {res['stats_reset']} игроков\n"
        f"✅ <b>Балансы игроков:</b> возвращены к исходному состоянию до ошибки!\n\n"
        f"🪙 <b>Актуальный эталонный топ:</b>\n{top_lines}")


@router.message(Cmd("п", "п.", "передать", "перевод", "дать", "передать монеты", "дать монеты", "перевод монет",
                    "передать коины", "дать коины", "передать граммы", "дать граммы", "pay", "give", section=S,
                    usage="п {ссылка} {сумма}", desc="Передать валюту 🪙"))
async def cmd_give(message: Message, bot: Bot, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    uid, name, rest = await resolve_target(message, args, bot)
    bal = await db.get_balance(message.from_user.id)
    amount = parse_amount(rest, bal, 1)

    if not had_prefix and in_group:
        if not uid or not amount or amount <= 0:
            return

    if not uid:
        return await message.reply("Укажите получателя: реплаем или @ником.\nПример: <code>п @user 5000</code> или <code>п 5000</code> ответом")
    if uid == message.from_user.id:
        return await message.reply("Себе передать нельзя 🙂")
    if not amount or amount <= 0:
        return await message.reply("Укажите сумму: <code>п @user 5000</code> или <code>п 5000</code> ответом")
    if amount > bal:
        return await message.reply(f"Недостаточно средств.\nВаш баланс: <b>{c(bal)}</b>")
    
    sender_bal = await db.add_balance(message.from_user.id, -amount, "give_out", str(uid))
    await db.add_balance(uid, amount, "give_in", str(message.from_user.id))
    await message.reply(
        f"✅ {mention(message.from_user)} ➡️ {mention_id(uid, name)}\n"
        f"Передано: <b>{c(amount)}</b>\n"
        f"Остаток на балансе: <b>{c(sender_bal)}</b>")



# ═══════════════ СИСТЕМА БИЗНЕСОВ И РЫНКА (30 ПРЕДПРИЯТИЙ ДО 100 LVL) ═══════════════
def _render_biz_menu(uid: int, user_biz: dict[str, dict], prof: dict, page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    lvl = prof["level"]
    now = int(time.time())

    # Подсчет дохода и накопленной прибыли
    total_income_min = 0
    accumulated_profit = 0
    owned_lines = []

    for k, info in BUSINESS_TYPES.items():
        cnt = user_biz.get(k, {}).get("count", 0)
        if cnt > 0:
            last_col = user_biz[k].get("last_collect", now)
            mins = min(24 * 60, max(0, int((now - last_col) // 60)))
            profit = mins * cnt * info["income_per_min"]
            total_income_min += cnt * info["income_per_min"]
            accumulated_profit += profit
            owned_lines.append(f"• {info['emoji']} <b>{info['name']}:</b> {cnt} шт. (доход: +{cnt*info['income_per_min']:,} 🪙/мин)")

    # 30 основных предприятий
    main_biz = [(k, v) for k, v in BUSINESS_TYPES.items() if "id" in v and 1 <= v["id"] <= 30]
    main_biz.sort(key=lambda x: x[1]["id"])
    total_pages = 3
    page = max(1, min(total_pages, page))

    start_idx = (page - 1) * 10
    end_idx = start_idx + 10
    page_biz = main_biz[start_idx:end_idx]

    market_lines = []
    for k, info in page_biz:
        buy_p, trend = get_market_price(k, is_sell=False)
        sell_p, _ = get_market_price(k, is_sell=True)
        lock = "🔒 " if lvl < info["req_lvl"] else "✅ "
        lvl_note = f"<i>(с {info['req_lvl']} LVL)</i>" if lvl < info["req_lvl"] else ""
        market_lines.append(
            f"{lock}{info['emoji']} <b>#{info['id']} {info['name']}</b> {lvl_note}\n"
            f"   Купить: <b>{c(buy_p)}</b> [{trend}] · Продать (б/у ~50%): <b>{c(sell_p)}</b>\n"
            f"   Доход: <code>+{info['income_per_min']:,} 🪙/мин</code>"
        )

    owned_txt = "\n".join(owned_lines) if owned_lines else "<i>У вас пока нет купленных предприятий.</i>"
    market_txt = "\n\n".join(market_lines)

    text = (
        f"🏢 <b>РЫНОК БИЗНЕСОВ И ИМУЩЕСТВА</b> 📈\n\n"
        f"🎮 <b>Ваш игровой уровень:</b> <b>{lvl} LVL</b> ({prof['xp']}/{prof['next_xp']} XP)\n"
        f"💵 <b>Суммарный доход:</b> <b>+{total_income_min:,} 🪙/мин</b>\n"
        f"💰 <b>Накоплено к сбору:</b> <b>+{accumulated_profit:,} 🪙</b>\n\n"
        f"📦 <b>Ваше имущество:</b>\n{owned_txt}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Каталог рынка (Страница {page}/{total_pages}):</b>\n\n"
        f"{market_txt}\n\n"
        f"💡 <i>Команды:</i> <code>купить [номер/название] [кол-во]</code> · <code>продать [название] [кол-во]</code> · <code>собрать</code>"
    )

    rows = [
        [InlineKeyboardButton(text=f"💰 Собрать прибыль (+{accumulated_profit:,} 🪙)", callback_data=f"biz:collect:{page}")],
    ]
    for i in range(0, len(page_biz), 2):
        row = []
        k1, b1 = page_biz[i]
        row.append(InlineKeyboardButton(text=f"{b1['emoji']} {b1['name'][:13]}", callback_data=f"biz:buy:{k1}:{page}"))
        if i + 1 < len(page_biz):
            k2, b2 = page_biz[i + 1]
            row.append(InlineKeyboardButton(text=f"{b2['emoji']} {b2['name'][:13]}", callback_data=f"biz:buy:{k2}:{page}"))
        rows.append(row)

    prev_p = max(1, page - 1)
    next_p = min(total_pages, page + 1)
    rows.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"biz:page:{prev_p}"),
        InlineKeyboardButton(text=f"📄 Стр. {page}/{total_pages}", callback_data=f"biz:refresh:{page}"),
        InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"biz:page:{next_p}"),
    ])
    rows.append([InlineKeyboardButton(text="🔄 Обновить рынок", callback_data=f"biz:refresh:{page}")])

    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("бизнесы", "бизнес", "предприятия", "имущество", "заводы", "фермы", "недвижимость", section=S,
                    usage="бизнесы", desc="Рынок предприятий, покупка и сбор прибыли"))
async def cmd_businesses(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type in {"group", "supergroup"} and (args or "").strip():
        return
    uid = message.from_user.id
    await _ensure_start(uid)
    user_biz = await db.get_user_businesses(uid)
    prof = await db.get_game_profile(uid)
    text, kb = _render_biz_menu(uid, user_biz, prof)
    await message.reply(text, reply_markup=kb)


@router.message(Cmd("собрать", "прибыль", "собрать прибыль", "снять прибыль", section=S,
                    usage="собрать", desc="Собрать накопленную прибыль с предприятий"))
async def cmd_collect_profit(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type in {"group", "supergroup"} and (args or "").strip():
        return
    uid = message.from_user.id
    await _ensure_start(uid)
    user_biz = await db.get_user_businesses(uid)
    if not user_biz:
        if not had_prefix and message.chat.type in {"group", "supergroup"}:
            return
        return await message.reply("У вас пока нет купленных предприятий. Купите что-нибудь в <code>бизнесы</code>!")

    now = int(time.time())
    total_collected = 0
    keys_to_update = []

    for k, data in user_biz.items():
        if k in BUSINESS_TYPES and data["count"] > 0:
            last_col = data.get("last_collect", now)
            mins = min(24 * 60, max(0, int((now - last_col) // 60)))
            if mins > 0:
                profit = mins * data["count"] * BUSINESS_TYPES[k]["income_per_min"]
                total_collected += profit
                keys_to_update.append(k)

    if total_collected <= 0:
        if not had_prefix and message.chat.type in {"group", "supergroup"}:
            return
        return await message.reply("⏳ Прибыль ещё не успела накопиться (начисление происходит каждую минуту).")

    await db.update_business_collect_time(uid, keys_to_update)
    new_bal = await db.add_coins(uid, total_collected, "biz_income")

    await message.reply(
        f"💰 <b>Прибыль успешно собрана!</b>\n\n"
        f"Начислено: <b>+{c(total_collected)}</b> 🎉\n"
        f"Ваш новый баланс: <b>{c(new_bal)}</b>"
    )


@router.message(Cmd("купить", "приобрести", "buy", section=S,
                    usage="купить {название} [кол-во]", desc="Купить предприятие на рынке"))
async def cmd_buy_business(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    await _ensure_start(uid)

    parts = (args or "").strip().split()
    if not parts:
        if not had_prefix and in_group:
            return
        return await message.reply(
            "🏢 <b>Покупка предприятий:</b>\n"
            "Формат: <code>купить [название] [кол-во]</code>\n"
            "Пример: <code>купить ферму 2</code> · <code>купить завод</code> · <code>купить дом</code>\n\n"
            "Весь каталог: <code>бизнесы</code>")

    # Распознавание названия и количества
    count = 1
    if parts[-1].isdigit():
        count = max(1, min(100, int(parts[-1])))
        name_q = " ".join(parts[:-1])
    else:
        name_q = " ".join(parts)

    biz_key, info = find_business_by_alias(name_q)
    if not biz_key:
        if not had_prefix and in_group:
            return
        return await message.reply("❌ Предприятие не найдено. Напишите <code>бизнесы</code>, чтобы посмотреть каталог.")

    prof = await db.get_game_profile(uid)
    if prof["level"] < info["req_lvl"]:
        return await message.reply(
            f"🔒 <b>Недостаточный игровой уровень!</b>\n\n"
            f"Для покупки {info['emoji']} <b>{info['name']}</b> требуется <b>{info['req_lvl']} LVL</b>.\n"
            f"Ваш текущий уровень: <b>{prof['level']} LVL</b>.\n"
            f"💡 Играйте в казино/дартс/кубик, чтобы прокачать уровень!")

    buy_price_unit, _ = get_market_price(biz_key, is_sell=False)
    total_cost = buy_price_unit * count
    bal = await db.get_coins(uid)

    if bal < total_cost:
        return await message.reply(
            f"❌ Недостаточно монет.\n"
            f"Стоимость: <b>{c(total_cost)}</b> (за {count} шт.)\n"
            f"Ваш баланс: <b>{c(bal)}</b>")

    await db.add_coins(uid, -total_cost, "biz_buy", biz_key)
    new_count = await db.change_user_business(uid, biz_key, count)
    new_bal = await db.get_coins(uid)
    try:
        core_backup.schedule_quick_backup(message.bot)
    except Exception:
        pass

    await message.reply(
        f"🎉 <b>Успешная покупка!</b>\n\n"
        f"Вы приобрели: {info['emoji']} <b>{info['name']}</b> × {count} шт.\n"
        f"Списано: <b>−{c(total_cost)}</b>\n"
        f"Всего у вас: <b>{new_count} шт.</b>\n"
        f"Доход: <b>+{new_count * info['income_per_min']:,} 🪙/мин</b>\n"
        f"Баланс: <b>{c(new_bal)}</b>"
    )


@router.message(Cmd("продать", "sell", section=S,
                    usage="продать {название} [кол-во]", desc="Продать предприятие на рынке"))
async def cmd_sell_business(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    uid = message.from_user.id
    await _ensure_start(uid)

    parts = (args or "").strip().split()
    if not parts:
        if not had_prefix and in_group:
            return
        return await message.reply("Формат: <code>продать [название] [кол-во]</code>\nПример: <code>продать завод 1</code>")

    count = 1
    if parts[-1].isdigit():
        count = max(1, int(parts[-1]))
        name_q = " ".join(parts[:-1])
    else:
        name_q = " ".join(parts)

    biz_key, info = find_business_by_alias(name_q)
    if not biz_key:
        if not had_prefix and in_group:
            return
        return await message.reply("❌ Предприятие не найдено. Напишите <code>бизнесы</code>.")

    user_biz = await db.get_user_businesses(uid)
    have = user_biz.get(biz_key, {}).get("count", 0)
    if have < count:
        return await message.reply(f"У вас нет столько предприятий. В наличии: <b>{have} шт.</b>")

    sell_price_unit, _ = get_market_price(biz_key, is_sell=True)
    total_gain = sell_price_unit * count

    await db.change_user_business(uid, biz_key, -count)
    new_bal = await db.add_coins(uid, total_gain, "biz_sell", biz_key)
    try:
        core_backup.schedule_quick_backup(message.bot)
    except Exception:
        pass

    await message.reply(
        f"🏷 <b>Предприятие ликвидировано!</b>\n\n"
        f"Вы продали: {info['emoji']} <b>{info['name']}</b> × {count} шт. <i>(вторичный рынок б/у: -50%)</i>\n"
        f"Выручка: <b>+{c(total_gain)}</b>\n"
        f"Ваш новый баланс: <b>{c(new_bal)}</b>"
    )


@router.callback_query(F.data.startswith("biz:"))
async def cb_businesses(call: CallbackQuery):
    uid = call.from_user.id
    parts = call.data.split(":")
    action = parts[1]

    # Определяем страницу
    cur_page = 1
    if action == "page" and len(parts) > 2 and parts[2].isdigit():
        cur_page = int(parts[2])
    elif action in ("refresh", "collect") and len(parts) > 2 and parts[2].isdigit():
        cur_page = int(parts[2])
    elif action == "buy" and len(parts) > 3 and parts[3].isdigit():
        cur_page = int(parts[3])

    if action in ("menu", "refresh", "page"):
        user_biz = await db.get_user_businesses(uid)
        prof = await db.get_game_profile(uid)
        text, kb = _render_biz_menu(uid, user_biz, prof, page=cur_page)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        return await call.answer(f"Страница {cur_page}/3")

    if action == "collect":
        user_biz = await db.get_user_businesses(uid)
        if not user_biz:
            return await call.answer("У вас нет предприятий!", show_alert=True)
        now = int(time.time())
        total = 0
        keys = []
        for k, data in user_biz.items():
            if k in BUSINESS_TYPES and data["count"] > 0:
                mins = min(24 * 60, max(0, int((now - data.get("last_collect", now)) // 60)))
                if mins > 0:
                    total += mins * data["count"] * BUSINESS_TYPES[k]["income_per_min"]
                    keys.append(k)
        if total <= 0:
            return await call.answer("⏳ Прибыль ещё не накопилась (начисляется каждую минуту).", show_alert=True)
        await db.update_business_collect_time(uid, keys)
        await db.add_coins(uid, total, "biz_income")
        try:
            core_backup.schedule_quick_backup(call.bot)
        except Exception:
            pass
        await call.answer(f"💰 Собрано: +{total:,} 🪙!", show_alert=True)
        # Обновляем меню на текущей странице
        user_biz = await db.get_user_businesses(uid)
        prof = await db.get_game_profile(uid)
        text, kb = _render_biz_menu(uid, user_biz, prof, page=cur_page)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        return

    if action == "buy":
        biz_key = parts[2]
        info = BUSINESS_TYPES.get(biz_key)
        if not info:
            return await call.answer("Ошибка")
        prof = await db.get_game_profile(uid)
        if prof["level"] < info["req_lvl"]:
            return await call.answer(f"🔒 Требуется {info['req_lvl']} LVL!", show_alert=True)
        buy_p, _ = get_market_price(biz_key, is_sell=False)
        bal = await db.get_coins(uid)
        if bal < buy_p:
            return await call.answer(f"Недостаточно монет! Нужно {buy_p:,} 🪙", show_alert=True)
        await db.add_coins(uid, -buy_p, "biz_buy", biz_key)
        await db.change_user_business(uid, biz_key, 1)
        try:
            core_backup.schedule_quick_backup(call.bot)
        except Exception:
            pass
        await call.answer(f"🎉 Куплено: {info['name']}!", show_alert=True)
        user_biz = await db.get_user_businesses(uid)
        text, kb = _render_biz_menu(uid, user_biz, prof, page=cur_page)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
        return



# ═══════════════ БИЗНЕС-АУКЦИОНЫ В ЧАТЕ ═══════════════
def get_business_tier(biz_key: str) -> str:
    """Определяет категорию бизнеса: cheap, mythic, legendary"""
    info = BUSINESS_TYPES.get(biz_key, {})
    biz_id = info.get("id", 1)
    if biz_id <= 10:
        return "cheap"
    elif biz_id <= 20:
        return "mythic"
    else:
        return "legendary"


TIER_TITLES = {
    "cheap": "🌱 Дешёвый / Обычный (1-10 LVL)",
    "mythic": "🔮 Мифический (11-20 LVL)",
    "legendary": "👑 Легендарный (21-30 LVL)",
}

_auction_votes: dict[int, dict[int, str]] = {}  # chat_id -> {user_id: tier}


def _render_auction_vote_kb(chat_id: int) -> InlineKeyboardMarkup:
    votes = _auction_votes.get(chat_id, {})
    c_count = sum(1 for t in votes.values() if t == "cheap")
    m_count = sum(1 for t in votes.values() if t == "mythic")
    l_count = sum(1 for t in votes.values() if t == "legendary")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🌱 Дешёвый ({c_count})", callback_data=f"auc_vote:{chat_id}:cheap"),
            InlineKeyboardButton(text=f"🔮 Мифический ({m_count})", callback_data=f"auc_vote:{chat_id}:mythic"),
            InlineKeyboardButton(text=f"👑 Легендарный ({l_count})", callback_data=f"auc_vote:{chat_id}:legendary"),
        ]
    ])


def _render_auction_voting_view(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    votes = _auction_votes.get(chat_id, {})
    total_votes = len(votes)
    c_count = sum(1 for t in votes.values() if t == "cheap")
    m_count = sum(1 for t in votes.values() if t == "mythic")
    l_count = sum(1 for t in votes.values() if t == "legendary")

    def _bar(cnt: int, tot: int) -> str:
        if tot <= 0:
            return "░░░░░░░░░░ 0%"
        pct = int(round((cnt / tot) * 100))
        filled = min(10, max(0, int(round((cnt / tot) * 10))))
        return f"{'█' * filled}{'░' * (10 - filled)} {pct}%"

    text = (
        "🗳 <b>ГОЛОСОВАНИЕ: КАТЕГОРИЯ СЛЕДУЮЩЕГО АУКЦИОНА</b> 🔨\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "Игроки беседы решают, какая категория предприятия выпадет на следующих торгах!\n\n"
        f"🌱 <b>Дешёвые / Обычные</b> (1–10 ур.):\n"
        f"<code>{_bar(c_count, total_votes)}</code> ({c_count} голосов)\n"
        "<i>Ферма, Дом, Завод, Торговый центр, Шахта, СТО...</i>\n\n"
        f"🔮 <b>Мифические</b> (11–20 ур.):\n"
        f"<code>{_bar(m_count, total_votes)}</code> ({m_count} голосов)\n"
        "<i>Корпорация, Сфера Дайсона, Марсианская база...</i>\n\n"
        f"👑 <b>Легендарные</b> (21–30 ур.):\n"
        f"<code>{_bar(l_count, total_votes)}</code> ({l_count} голосов)\n"
        "<i>Квантовый мир, Галактическая империя...</i>\n\n"
        f"👥 Всего голосов: <b>{total_votes}</b>\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        "👇 <b>Нажмите на кнопку с категорией, чтобы проголосовать:</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🌱 Дешёвый (1-10 ур) · {c_count}", callback_data=f"auc_vote:{chat_id}:cheap")],
        [InlineKeyboardButton(text=f"🔮 Мифический (11-20 ур) · {m_count}", callback_data=f"auc_vote:{chat_id}:mythic")],
        [InlineKeyboardButton(text=f"👑 Легендарный (21-30 ур) · {l_count}", callback_data=f"auc_vote:{chat_id}:legendary")],
        [InlineKeyboardButton(text="🔄 Обновить результаты", callback_data=f"auc_vote_rf:{chat_id}")]
    ])
    return text, kb


class ChatAuction:
    def __init__(self, chat_id: int, biz_key: str, start_bid: int, duration_sec: int = 600, tier_name: str = "Обычный"):
        self.chat_id = chat_id
        self.biz_key = biz_key
        self.start_bid = start_bid
        self.current_bid = start_bid
        self.has_bids = False
        self.highest_bidder_id: int | None = None
        self.highest_bidder_name: str | None = None
        self.end_ts = int(time.time()) + duration_sec
        self.msg_id: int | None = None
        self.thread_id: int | None = None
        self.task: asyncio.Task | None = None
        self.tier_name: str = tier_name


_active_auctions: dict[int, ChatAuction] = {}


def _render_auction_card(auc: ChatAuction) -> tuple[str, InlineKeyboardMarkup]:
    info = BUSINESS_TYPES.get(auc.biz_key, {})
    name = info.get("name", auc.biz_key)
    emoji = info.get("emoji", "🏢")
    base = info.get("base_price", 0)
    income = info.get("income_per_min", 0)

    now = int(time.time())
    left_sec = max(0, auc.end_ts - now)

    if auc.has_bids and auc.highest_bidder_id:
        leader_str = f"👑 {mention_id(auc.highest_bidder_id, auc.highest_bidder_name or 'Игрок')} (<b>{c(auc.current_bid)}</b>)"
    else:
        leader_str = "<i>Пока нет ставок (стартовая цена)</i>"

    step1 = max(100, int(auc.current_bid * 0.05))
    step2 = max(500, int(auc.current_bid * 0.15))
    step3 = max(1000, int(auc.current_bid * 0.35))

    tier_label = getattr(auc, "tier_name", "Обычный")

    text = (
        f"🏛 <b>БИЗНЕС-АУКЦИОН В ЧАТЕ!</b> 🔨\n"
        f"✦ ══ • ⊰ 💎 🏢 ⚡️ 🛰 🚀 🏦 ⊱ • ══ ✦\n\n"
        f"🏷 <b>Категория лота:</b> <b>{tier_label}</b>\n"
        f"📦 <b>Выставленный лот:</b> {emoji} <b>{name}</b>\n"
        f"🏷 <b>Рыночная цена:</b> <b>{c(base)}</b>\n"
        f"💵 <b>Пассивный доход:</b> <code>+{income:,} 🪙/мин</code>\n\n"
        f"💰 <b>Текущая ставка:</b> <b>{c(auc.current_bid)}</b>\n"
        f"👤 <b>Лидер аукциона:</b> {leader_str}\n"
        f"⏳ <b>До завершения торгов:</b> <b>{left_sec} сек.</b>\n\n"
        f"⚠️ <i>Правило: игроки, у которых уже есть это предприятие, не могут участвовать!</i>\n\n"
        f"💡 <i>Перебить ставку:</i> напишите <code>ставка [сумма]</code>\n"
        f"<i>(например, <code>ставка {auc.current_bid + step1}</code>) или нажмите кнопки ниже:</i>"
    )

    rows = [
        [
            InlineKeyboardButton(text=f"➕ {step1:,} 🪙", callback_data=f"auc_bid:{auc.chat_id}:{step1}"),
            InlineKeyboardButton(text=f"➕ {step2:,} 🪙", callback_data=f"auc_bid:{auc.chat_id}:{step2}"),
            InlineKeyboardButton(text=f"➕ {step3:,} 🪙", callback_data=f"auc_bid:{auc.chat_id}:{step3}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"auc_refresh:{auc.chat_id}"),
        ]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _auction_timer_task(bot: Bot, chat_id: int):
    while True:
        await asyncio.sleep(5)
        auc = _active_auctions.get(chat_id)
        if not auc:
            break
        now = int(time.time())
        if now >= auc.end_ts:
            _active_auctions.pop(chat_id, None)
            info = BUSINESS_TYPES.get(auc.biz_key, {})
            name = info.get("name", auc.biz_key)
            emoji = info.get("emoji", "🏢")

            if auc.has_bids and auc.highest_bidder_id:
                user_biz = await db.get_user_businesses(auc.highest_bidder_id)
                if user_biz.get(auc.biz_key, {}).get("count", 0) > 0:
                    # У игрока уже есть такой бизнес — отменяем и возвращаем ставку
                    await db.add_coins(auc.highest_bidder_id, auc.current_bid, "auction_refund", auc.biz_key)
                    win_text = (
                        f"⚠️ <b>Аукцион завершён без передачи лота!</b>\n\n"
                        f"Лидер торгов {mention_id(auc.highest_bidder_id, auc.highest_bidder_name or 'Игрок')} уже имеет в собственности {emoji} <b>{name}</b>.\n"
                        f"Ставка <b>{c(auc.current_bid)}</b> полностью возвращена на баланс."
                    )
                else:
                    await db.change_user_business(auc.highest_bidder_id, auc.biz_key, 1)
                    try:
                        core_backup.schedule_quick_backup(bot)
                    except Exception:
                        pass
                    win_text = (
                        f"🔨 💥 <b>АУКЦИОН ЗАВЕРШЁН! ПРОДАНО!</b> 💥 🔨\n\n"
                        f"👑 <b>Победитель:</b> {mention_id(auc.highest_bidder_id, auc.highest_bidder_name or 'Игрок')}\n"
                        f"🏆 <b>Выигранный лот:</b> {emoji} <b>{name}</b> за <b>{c(auc.current_bid)}</b>!\n\n"
                        f"🎉 Предприятие перешло в вашу собственность! Прибыль начисляется каждую минуту (<code>бизнесы</code>)."
                    )
            else:
                win_text = (
                    f"⌛️ <b>Аукцион завершён!</b>\n\n"
                    f"📦 Лот {emoji} <b>{name}</b> снят с торгов, так как никто не сделал начальную ставку <b>{c(auc.start_bid)}</b>."
                )

            # Добавляем интерактивное голосование за лот следующего аукциона!
            vote_kb = _render_auction_vote_kb(chat_id)
            win_text += "\n\n🗳 <b>Голосуйте, какую категорию бизнеса выставить на следующий аукцион:</b>"

            try:
                await bot.send_message(chat_id, win_text, reply_markup=vote_kb, message_thread_id=auc.thread_id)
            except Exception:
                pass
            break


async def start_chat_auction(bot: Bot, chat_id: int, biz_key: str | None = None, thread_id: int | None = None) -> bool:
    if not await casino_enabled(chat_id):
        return False
    if chat_id in _active_auctions:
        return False

    votes = _auction_votes.get(chat_id, {})
    chosen_tier = None
    if not biz_key or biz_key not in BUSINESS_TYPES:
        if votes:
            c_cnt = sum(1 for t in votes.values() if t == "cheap")
            m_cnt = sum(1 for t in votes.values() if t == "mythic")
            l_cnt = sum(1 for t in votes.values() if t == "legendary")
            best_cnt = max(c_cnt, m_cnt, l_cnt)
            candidates = []
            if c_cnt == best_cnt:
                candidates.append("cheap")
            if m_cnt == best_cnt:
                candidates.append("mythic")
            if l_cnt == best_cnt:
                candidates.append("legendary")
            chosen_tier = random.choice(candidates)
        else:
            # Сбалансированный шанс: дешёвые и доступные бизнесы падают регулярно!
            chosen_tier = random.choices(["cheap", "mythic", "legendary"], weights=[40, 35, 25])[0]

        tier_biz_keys = [k for k in BUSINESS_TYPES.keys() if get_business_tier(k) == chosen_tier]
        biz_key = random.choice(tier_biz_keys)
    else:
        chosen_tier = get_business_tier(biz_key)

    # сбрасываем голоса после старта
    _auction_votes.pop(chat_id, None)

    info = BUSINESS_TYPES[biz_key]
    tier_label = TIER_TITLES.get(chosen_tier, "Обычный")
    start_bid = max(100, int(info["base_price"] * 0.40))

    if thread_id is None:
        thread_id = await get_gram_topic(chat_id)

    auc = ChatAuction(chat_id=chat_id, biz_key=biz_key, start_bid=start_bid, duration_sec=600, tier_name=tier_label)
    auc.thread_id = thread_id
    _active_auctions[chat_id] = auc

    text, kb = _render_auction_card(auc)
    try:
        msg = await bot.send_message(chat_id, text, reply_markup=kb, message_thread_id=thread_id)
        auc.msg_id = msg.message_id
    except Exception:
        _active_auctions.pop(chat_id, None)
        return False

    auc.task = asyncio.create_task(_auction_timer_task(bot, chat_id))
    return True


async def place_auction_bid(bot: Bot, chat_id: int, user_id: int, user_name: str, bid_amount: int) -> tuple[bool, str]:
    if not await casino_enabled(chat_id):
        return False, "Казино и азартные игры отключены в этом чате."

    auc = _active_auctions.get(chat_id)
    if not auc:
        return False, "В этом чате сейчас нет активного аукциона."

    # Проверка: если у человека уже есть это предприятие — не даём делать ставку!
    user_biz = await db.get_user_businesses(user_id)
    have_count = user_biz.get(auc.biz_key, {}).get("count", 0)
    if have_count > 0:
        info = BUSINESS_TYPES.get(auc.biz_key, {})
        return False, f"❌ У вас уже есть {info.get('emoji', '🏢')} <b>{info.get('name', 'это предприятие')}</b> ({have_count} шт.)!\nНа аукционе можно бороться только за те предприятия, которых у вас ещё нет."

    now = int(time.time())
    if now >= auc.end_ts:
        return False, "Время аукциона истекло!"

    min_required = (auc.current_bid + 1) if auc.has_bids else auc.start_bid
    if bid_amount < min_required:
        return False, f"Ставка слишком мала! Минимальная ставка: <b>{c(min_required)}</b>."

    bal = await db.get_coins(user_id)
    if bal < bid_amount:
        return False, f"Недостаточно монет на балансе!\nУ вас: <b>{c(bal)}</b>, а ставка: <b>{c(bid_amount)}</b>."

    prev_bidder = auc.highest_bidder_id
    prev_bid = auc.current_bid

    # Списываем ставку
    await db.add_coins(user_id, -bid_amount, "auction_bid", auc.biz_key)

    # Если был предыдущий лидер и это другой игрок — возвращаем ему монеты
    if auc.has_bids and prev_bidder:
        await db.add_coins(prev_bidder, prev_bid, "auction_refund", auc.biz_key)

    auc.current_bid = bid_amount
    auc.has_bids = True
    auc.highest_bidder_id = user_id
    auc.highest_bidder_name = user_name

    # Анти-снайп продление (+60 секунд если < 60 сек)
    if auc.end_ts - now < 60:
        auc.end_ts = now + 60

    # Обновляем карточку
    if auc.msg_id:
        text, kb = _render_auction_card(auc)
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=auc.msg_id, reply_markup=kb)
        except Exception:
            pass

    return True, f"✅ Ваша ставка <b>{c(bid_amount)}</b> принята! Вы новый лидер аукциона!"


async def auction_schedule_worker(bot: Bot):
    """Фоновый воркер: периодически проводит бизнес-аукционы в активных чатах."""
    while True:
        try:
            await asyncio.sleep(60)
            now = int(time.time())
            chats = await db.fetchall("SELECT chat_id FROM chats WHERE silent=0")
            for c_row in chats:
                cid = c_row["chat_id"]
                if not await casino_enabled(cid):
                    continue
                if cid in _active_auctions:
                    continue

                int_hours_str = await db.get_setting(cid, "auction_interval", "3")
                if int_hours_str in ("0", "выкл", "off", "disable"):
                    continue
                try:
                    int_hours = max(1, int(int_hours_str))
                except Exception:
                    int_hours = 3

                interval_sec = int_hours * 3600
                last_auc_str = await db.get_setting(cid, "last_auction_ts", "0")
                try:
                    last_auc = int(last_auc_str)
                except Exception:
                    last_auc = 0

                if (now - last_auc) >= interval_sec:
                    await db.set_setting(cid, "last_auction_ts", str(now))
                    await start_chat_auction(bot, cid)
        except Exception:
            pass


@router.message(Cmd("бизнес аукцион", "аукцион бизнесов", "бизнесаукцион", "аукцион", section=S,
                    usage="аукцион [старт/стоп/интервал]", desc="Бизнес-аукцион предприятий в чате"))
async def cmd_business_auction(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    if not in_group:
        return await message.reply("🏛 Бизнес-аукционы проводятся в беседах между игроками!")

    if not await casino_enabled(message.chat.id):
        if had_prefix or (args or "").strip():
            return await message.reply("🎰 Казино и аукционы отключены в этом чате. Включить: <code>+казино</code>")
        return

    parts = (args or "").strip().split()
    sub = parts[0].lower() if parts else ""

    from core_ranks import effective_rank
    have_rank = await effective_rank(message, bot)

    if sub in ("старт", "start", "запуск", "начать"):
        if have_rank < 3:
            return await message.reply("🔒 Запуск аукциона вручную доступен администраторам (3+ ранг).")
        if message.chat.id in _active_auctions:
            return await message.reply("⚠️ В чате уже идёт активный аукцион!")

        target_biz = parts[1].lower() if len(parts) > 1 else None
        biz_key, _ = find_business_by_alias(target_biz) if target_biz else (None, None)
        ok = await start_chat_auction(bot, message.chat.id, biz_key, thread_id=_tid(message))
        if not ok:
            return await message.reply("Не удалось запустить аукцион (проверьте тему или настройки казино).")
        return

    elif sub in ("стоп", "stop", "отмена", "cancel"):
        if have_rank < 3:
            return await message.reply("🔒 Отмена аукциона доступна администраторам (3+ ранг).")
        auc = _active_auctions.pop(message.chat.id, None)
        if not auc:
            return await message.reply("Сейчас нет активного аукциона.")
        if auc.task:
            auc.task.cancel()
        if auc.has_bids and auc.highest_bidder_id:
            await db.add_coins(auc.highest_bidder_id, auc.current_bid, "auction_cancel_refund", auc.biz_key)
        return await message.reply(f"🛑 <b>Аукцион отменён администратором.</b>\nСтавки возвращены игрокам.")

    elif sub in ("интервал", "время", "период"):
        if have_rank < 3:
            return await message.reply("🔒 Настройка интервала доступна администраторам (3+ ранг).")
        val = parts[1].lower() if len(parts) > 1 else ""
        if val in ("выкл", "off", "0", "disable"):
            await db.set_setting(message.chat.id, "auction_interval", "0")
            return await message.reply("🛑 Автоматические аукционы в чате отключены. Запуск только вручную: <code>аукцион старт</code>")
        elif val.isdigit():
            h = max(1, min(24, int(val)))
            await db.set_setting(message.chat.id, "auction_interval", str(h))
            return await message.reply(f"✅ Интервал авто-аукционов установлен: <b>каждые {h} ч.</b>")
        else:
            cur = await db.get_setting(message.chat.id, "auction_interval", "3")
            return await message.reply(
                f"⚙️ Текущий интервал авто-аукционов: <b>{cur} ч.</b>\n"
                f"Изменить: <code>аукцион интервал 2</code> (каждые 2 часа) или <code>аукцион интервал выкл</code>"
            )

    auc = _active_auctions.get(message.chat.id)
    if auc:
        text, kb = _render_auction_card(auc)
        return await message.reply(text, reply_markup=kb)
    else:
        cur_int = await db.get_setting(message.chat.id, "auction_interval", "3")
        int_desc = f"каждые {cur_int} ч." if cur_int != "0" else "отключен (запуск вручную)"
        return await message.reply(
            f"🏛 <b>БИЗНЕС-АУКЦИОН ЧАТА</b> 🔨\n\n"
            f"Сейчас на торгах нет активного лота.\n"
            f"⏰ Автоматический запуск: <b>{int_desc}</b>\n\n"
            f"💡 <i>Администраторы могут запустить аукцион вручную:</i>\n"
            f"• <code>аукцион старт</code> — случайное предприятие\n"
            f"• <code>аукцион старт шахта</code> — выставить конкретный лот\n"
            f"• <code>аукцион интервал [часы/выкл]</code> — настройка периода\n\n"
            f"💰 <i>Делать ставки:</i> <code>ставка [сумма]</code> во время торгов!"
        )


@router.message(Cmd("ставка", "бид", "перебить", section=S,
                    usage="ставка [сумма]", desc="Сделать ставку на бизнес-аукционе"))
async def cmd_auction_bid(message: Message, bot: Bot, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    if not in_group:
        return await message.reply("Ставки на аукционе принимаются только в группе!")

    if not await casino_enabled(message.chat.id):
        return

    auc = _active_auctions.get(message.chat.id)
    if not auc:
        if had_prefix:
            return await message.reply("В чате сейчас нет активного аукциона. Запуск: <code>аукцион старт</code>")
        return

    raw = (args or "").strip()
    if not raw:
        return await message.reply(f"Укажите сумму ставки: <code>ставка {auc.current_bid + 5000}</code>")

    bal = await db.get_coins(message.from_user.id)
    amount = parse_amount(raw, bal, 1)
    if not amount or amount <= 0:
        return await message.reply(f"Укажите корректную сумму ставки: <code>ставка {auc.current_bid + 5000}</code>")

    uname = message.from_user.first_name or f"Игрок {message.from_user.id}"
    ok, err_msg = await place_auction_bid(bot, message.chat.id, message.from_user.id, uname, amount)
    await message.reply(err_msg)


@router.callback_query(F.data.startswith("auc_bid:"))
async def cb_auction_bid(call: CallbackQuery, bot: Bot):
    parts = call.data.split(":")
    cid = int(parts[1])
    add_amt = int(parts[2])

    auc = _active_auctions.get(cid)
    if not auc:
        return await call.answer("Аукцион уже завершён!", show_alert=True)

    uname = call.from_user.first_name or f"Игрок {call.from_user.id}"
    new_bid = (auc.current_bid + add_amt) if auc.has_bids else max(auc.start_bid, auc.current_bid + add_amt)

    ok, msg = await place_auction_bid(bot, cid, call.from_user.id, uname, new_bid)
    await call.answer(msg.replace("<b>", "").replace("</b>", "").replace("✅ ", "").replace("❌ ", ""), show_alert=not ok)


@router.callback_query(F.data.startswith("auc_refresh:"))
async def cb_auction_refresh(call: CallbackQuery):
    cid = int(call.data.split(":")[1])
    auc = _active_auctions.get(cid)
    if not auc:
        return await call.answer("Аукцион завершён!", show_alert=True)

    text, kb = _render_auction_card(auc)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer("Статус обновлён")


@router.callback_query(F.data.startswith("auc_vote:"))
async def cb_auction_vote(call: CallbackQuery):
    parts = call.data.split(":")
    cid = int(parts[1])
    tier = parts[2]
    uid = call.from_user.id
    if tier not in ("cheap", "mythic", "legendary"):
        return await call.answer("Неверная категория", show_alert=True)

    if cid not in _auction_votes:
        _auction_votes[cid] = {}
    _auction_votes[cid][uid] = tier

    tier_title = TIER_TITLES.get(tier, tier)
    await call.answer(f"✅ Ваш голос принят: {tier_title}!", show_alert=True)

    text_body = getattr(call.message, "text", "") or ""
    if "ГОЛОСОВАНИЕ: КАТЕГОРИЯ" in text_body:
        text, kb = _render_auction_voting_view(cid)
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
    else:
        vote_kb = _render_auction_vote_kb(cid)
        try:
            await call.message.edit_reply_markup(reply_markup=vote_kb)
        except Exception:
            pass


@router.callback_query(F.data.startswith("auc_vote_rf:"))
async def cb_auction_vote_refresh(call: CallbackQuery):
    cid = int(call.data.split(":")[1])
    text, kb = _render_auction_voting_view(cid)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer("Результаты голосования обновлены!")


@router.message(Cmd("аукцион голос", "голос аукцион", "аук голос", "голос аукциона",
                    "аукцион голосование", "голосование аукцион", "выбор аукциона",
                    "аукцион кнопки", "аукцион категории",
                    section=S, usage="аукцион голос [дешёвый/мифический/легендарный]",
                    desc="Голосовать за категорию бизнеса на следующем аукционе"))
async def cmd_auction_vote_message(message: Message, bot: Bot, args: str = "", **kw):
    raw = (args or "").strip().lower()
    cid = message.chat.id
    uid = message.from_user.id

    tier = None
    if any(w in raw for w in ("деш", "дешев", "дешевый", "cheap", "1")):
        tier = "cheap"
    elif any(w in raw for w in ("миф", "мифич", "мифический", "mythic", "2")):
        tier = "mythic"
    elif any(w in raw for w in ("лег", "легенд", "легендарный", "legendary", "3")):
        tier = "legendary"

    if tier:
        if cid not in _auction_votes:
            _auction_votes[cid] = {}
        _auction_votes[cid][uid] = tier

    text, kb = _render_auction_voting_view(cid)
    if tier:
        tier_title = TIER_TITLES.get(tier, tier)
        await message.reply(
            f"✅ Ваш голос учтён: <b>{tier_title}</b>!\n\n" + text,
            reply_markup=kb
        )
    else:
        await message.reply(text, reply_markup=kb)


# ═══════════════ СПИСОК ИГР ═══════════════
GAMES_TEXT = f"""🎮 <b>ДОСТУПНЫЕ ИГРЫ НА МОНЕТЫ 🪙</b>

🎰 <b>СЛОТЫ / КАЗИНО</b> — <code>казик 1000</code> / <code>слоты 1к</code>
   Крути барабан · до x10

🪙 <b>ОРЁЛ / РЕШКА</b> — <code>орёл 1000</code> / <code>решка 1к</code>
   Угадай сторону монеты · x2

💣 <b>МИНЫ</b> — <code>мины 1000</code>
   Открывай клетки, не наткнись на мину · до x24

🎯 <b>ДАРТС</b> — <code>дартс 1000</code>
   Бросок в мишень · до x3

💥 <b>КРАШ</b> — <code>краш 1000</code>
   Множитель растёт — успей забрать · до x50

🎡 <b>КОЛЕСО</b> — <code>колесо 1000</code>
   Барабан удачи · до x10

🎲 <b>КУБИК / КОСТИ</b> — <code>куб 1000</code>
   Бросок костей с ботом · x2

💣 <b>САПЁР</b> — <code>сапёр 1000</code>
   Дуэль на двоих (ответом на сообщение друга)

🎡 <b>РУЛЕТКА</b> — <code>рулетка красное 1000</code>
   Цвет x2 · число x14

🃏 <b>БЛЭКДЖЕК / 21 ОЧКО</b> — <code>бд 1000</code> / <code>блэкджек 1к</code> / <code>21 1000</code>
   Интерактивная игра с Мокси · Натуральный блэкджек x2.5

🏇 <b>СКАЧКИ / ИППОДРОМ</b> — <code>скачки 1 1000</code> / <code>ипподром</code>
   5 скакунов · коэффициенты до x15 · ставки для всех игроков

🚀 <i>За каждую игру вы получаете опыт XP и повышаете уровень для покупки заводов и ферм!</i>"""


@router.message(Cmd("игры", "список игр", "games", "казик инфо", section=S, usage="игры",
                    desc="Список всех игр на монеты"))
async def cmd_games(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    if not had_prefix and message.chat.type in {"group", "supergroup"} and (args or "").strip():
        return
    from h_webapp import _get_webapp_kb
    await message.reply(GAMES_TEXT, reply_markup=_get_webapp_kb())


# ═══════════════ МИНИ-ИГРЫ НА КОМЕТЫ ═══════════════

# 1. Орёл и Решка
@router.message(Cmd("орёл", "орел", "решка", "монетка", section=S,
                    usage="орёл {ставка}", desc="Орёл или решка (x2)"))
async def cmd_coin(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    side = "орёл" if "ор" in (message.text or "").lower() else "решка"
    await db.add_comets(uid, -bet, "gram_bet_coin")
    flip = random.choice(["орёл", "решка"])
    is_win = flip == side
    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_note = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""
    kb = make_game_replay_kb("coin", bet, uid, side)
    if is_win:
        win = bet * 2
        bal = await db.add_comets(uid, win, "gram_win_coin")
        await message.reply(
            f"🪙 Выпал <b>{flip}</b>!\n\n"
            f"🎉 <b>ПОБЕДА! +{c(bet)}</b>\n"
            f"Баланс: <b>{c(bal)}</b>{lvl_note}", reply_markup=kb)
    else:
        bal = await db.get_comets(uid)
        await message.reply(
            f"🪙 Выпал <b>{flip}</b>\n\n"
            f"💔 Проигрыш −{c(bet)}\n"
            f"Баланс: <b>{c(bal)}</b>{lvl_note}", reply_markup=kb)


# 2. Мины
_mines: dict[str, dict] = {}
MINE_MULT = [1.1, 1.25, 1.5, 1.9, 2.5, 3.4, 4.8, 7.0, 11.0, 18.0, 32.0, 65.0]


def _mines_kb(key: str, state: dict, over: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for r in range(4):
        row = []
        for col in range(4):
            idx = r * 4 + col
            if idx in state["opened"]:
                row.append(InlineKeyboardButton(text="💎", callback_data="h:noop"))
            elif over and idx in state["bombs"]:
                row.append(InlineKeyboardButton(text="💣", callback_data="h:noop"))
            elif over:
                row.append(InlineKeyboardButton(text="▫️", callback_data="h:noop"))
            else:
                row.append(InlineKeyboardButton(text="⬛", callback_data=f"mine:{key}:{idx}"))
        rows.append(row)
    if not over and state["opened"]:
        mult = MINE_MULT[min(len(state["opened"]) - 1, len(MINE_MULT) - 1)]
        cash = int(state["bet"] * mult)
        rows.append([InlineKeyboardButton(
            text=f"💰 Забрать {c(cash)} (x{mult})", callback_data=f"mine:{key}:cash")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Cmd("мины", "mines", section=S, usage="мины {ставка}",
                    desc="Поле 4x4, 3 мины · до x24"))
async def cmd_mines(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    await db.add_comets(uid, -bet, "gram_bet_mines")
    bombs = set(random.sample(range(16), 3))
    key = f"{message.chat.id}:{uid}:{int(time.time()*1000)}"
    st = {"bet": bet, "uid": uid, "bombs": bombs, "opened": set()}
    _mines[key] = st
    await message.reply(
        f"💣 <b>МИНЫ (3 мины на поле)</b>\n"
        f"Ставка: <b>{c(bet)}</b>\n\n"
        f"Открывайте клетки! 💎 увеличивает множитель.",
        reply_markup=_mines_kb(key, st))


@router.callback_query(F.data.startswith("mine:"))
async def cb_mine(call: CallbackQuery):
    parts = call.data.split(":")
    key = f"{parts[1]}:{parts[2]}:{parts[3]}"
    st = _mines.get(key)
    if not st:
        return await call.answer("Игра устарела.")
    if call.from_user.id != st["uid"]:
        return await call.answer("Это не ваша игра!", show_alert=True)

    action = parts[4]
    if action == "cash":
        _mines.pop(key, None)
        mult = MINE_MULT[min(len(st["opened"]) - 1, len(MINE_MULT) - 1)]
        win = int(st["bet"] * mult)
        bal = await db.add_comets(st["uid"], win, "gram_win_mines")
        lvl, lvl_up = await db.add_game_xp(st["uid"], 1, is_win=True)
        lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        await call.message.edit_text(
            f"💰 <b>ВЫИГРЫШ ЗАБРАН!</b> x{mult}\n\n"
            f"Начислено: <b>+{c(win - st['bet'])}</b>\n"
            f"Баланс: <b>{c(bal)}</b>{lvl_note}",
            reply_markup=_mines_kb(key, st, over=True))
        return await call.answer("Победа!")

    idx = int(action)
    if idx in st["opened"]:
        return await call.answer()

    if idx in st["bombs"]:
        _mines.pop(key, None)
        bal = await db.get_comets(st["uid"])
        await db.add_game_xp(st["uid"], 1, is_win=False)
        await call.message.edit_text(
            f"💥 <b>БА-БАХ! Вы наступили на мину.</b>\n\n"
            f"Проигрыш: <b>−{c(st['bet'])}</b>\n"
            f"Баланс: <b>{c(bal)}</b>",
            reply_markup=_mines_kb(key, st, over=True))
        return await call.answer("Взрыв!", show_alert=True)

    st["opened"].add(idx)
    if len(st["opened"]) >= 13:
        _mines.pop(key, None)
        mult = MINE_MULT[-1]
        win = int(st["bet"] * mult)
        bal = await db.add_comets(st["uid"], win, "gram_win_mines")
        lvl, lvl_up = await db.add_game_xp(st["uid"], 2, is_win=True)
        lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
        await call.message.edit_text(
            f"🏆 <b>ПОЛЕ ПОЛНОСТЬЮ ОЧИЩЕНО!</b> x{mult}\n\n"
            f"Выигрыш: <b>+{c(win - st['bet'])}</b>\nБаланс: <b>{c(bal)}</b>{lvl_note}",
            reply_markup=_mines_kb(key, st, over=True))
        return await call.answer("Идеально!")

    mult = MINE_MULT[min(len(st["opened"]) - 1, len(MINE_MULT) - 1)]
    await call.message.edit_text(
        f"💣 <b>МИНЫ</b>\nСтавка: <b>{c(st['bet'])}</b> · "
        f"Открыто: <b>{len(st['opened'])}</b> · Множитель: <b>x{mult}</b>",
        reply_markup=_mines_kb(key, st))
    await call.answer(f"💎 x{mult}")


# 3. Дартс на кометы
@router.message(Cmd("дартс кометы", "дартс", "darts", section=S, usage="дартс {ставка}",
                    desc="🎯 Бросок в мишень · до x3"))
async def cmd_darts(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    await db.add_comets(uid, -bet, "gram_bet_darts")
    m = await message.answer_dice(emoji="🎯")
    await asyncio.sleep(3.5)
    v = m.dice.value
    mult = {6: 3.0, 5: 2.0, 4: 1.5, 3: 1.0}.get(v, 0)
    names = {6: "🎯 В яблочко!", 5: "Почти центр", 4: "Хорошо",
             3: "Задел мишень", 2: "Край", 1: "Мимо"}
    is_win = mult > 1.0
    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
    if mult:
        win = int(bet * mult)
        bal = await db.add_comets(uid, win, "gram_win_darts")
        diff = win - bet
        res = (f"🎉 <b>+{c(diff)}</b>" if diff > 0 else "🔸 Ставка возвращена")
        await message.reply(f"🎯 {names[v]} (x{mult})\n\n{res}\nБаланс: <b>{c(bal)}</b>{lvl_note}")
    else:
        bal = await db.get_comets(uid)
        await message.reply(f"🎯 {names.get(v, 'Мимо')}\n\n"
                            f"💔 Проигрыш −{c(bet)}\nБаланс: <b>{c(bal)}</b>{lvl_note}")


# 4. Краш
_crash: dict[str, dict] = {}


@router.message(Cmd("краш", "crash", section=S, usage="краш {ставка}",
                    desc="💥 Множитель растёт — успей забрать"))
async def cmd_crash(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    await db.add_comets(uid, -bet, "gram_bet_crash")

    r = random.random()
    if r < 0.03:
        crash_at = round(random.uniform(10, 50), 2)
    elif r < 0.25:
        crash_at = round(random.uniform(3, 10), 2)
    elif r < 0.65:
        crash_at = round(random.uniform(1.5, 3), 2)
    else:
        crash_at = round(random.uniform(1.0, 1.5), 2)

    key = f"{message.chat.id}:{uid}:{int(time.time()*1000)}"
    _crash[key] = {"bet": bet, "uid": uid, "crash": crash_at,
                   "cashed": False, "over": False}

    msg = await message.reply(
        f"🚀 <b>КРАШ</b> · Ставка: <b>{c(bet)}</b>\n\n"
        f"Множитель: <b>x1.00</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data=f"cr:{key}:cash")]]))

    mults = [1.1, 1.25, 1.5, 1.8, 2.2, 2.7, 3.5, 4.5, 6.0, 8.0, 12.0, 20.0, 35.0, 50.0]
    cur = 1.0
    for target in mults:
        await asyncio.sleep(1.2)
        st = _crash.get(key)
        if not st or st["cashed"]:
            return
        if target > crash_at:
            st["over"] = True
            _crash.pop(key, None)
            bal = await db.get_comets(uid)
            await db.add_game_xp(uid, 1, is_win=False)
            try:
                await msg.edit_text(
                    f"💥 <b>КРАШ НА x{crash_at:.2f}!</b>\n\n"
                    f"Вы не успели забрать.\n"
                    f"Проигрыш: <b>−{c(bet)}</b>\nБаланс: <b>{c(bal)}</b>")
            except Exception:
                pass
            return
        cur = target
        st["cur"] = cur
        try:
            await msg.edit_text(
                f"🚀 <b>КРАШ</b> · Ставка: <b>{c(bet)}</b>\n\n"
                f"Множитель: <b>x{cur:.2f}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=f"💰 ЗАБРАТЬ x{cur:.2f} (+{c(int(bet*cur)-bet)})",
                        callback_data=f"cr:{key}:cash")]]))
        except Exception:
            pass


@router.callback_query(F.data.startswith("cr:"))
async def cb_crash(call: CallbackQuery):
    parts = call.data.split(":")
    key = f"{parts[1]}:{parts[2]}:{parts[3]}"
    st = _crash.get(key)
    if not st or st["cashed"] or st["over"]:
        return await call.answer("Игра завершена.")
    if call.from_user.id != st["uid"]:
        return await call.answer("Это не ваша игра!", show_alert=True)
    st["cashed"] = True
    _crash.pop(key, None)
    cur = st.get("cur", 1.1)
    win = int(st["bet"] * cur)
    bal = await db.add_comets(st["uid"], win, "gram_win_crash")
    lvl, lvl_up = await db.add_game_xp(st["uid"], 1, is_win=True)
    lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
    await call.message.edit_text(
        f"🎉 <b>УСПЕЛ ЗАБРАТЬ!</b>\n\n"
        f"Множитель: <b>x{cur:.2f}</b>\n"
        f"Выигрыш: <b>+{c(win - st['bet'])}</b>\n"
        f"Баланс: <b>{c(bal)}</b>{lvl_note}")
    await call.answer(f"Забрано x{cur:.2f}!")


# 5. Колесо фортуны
WHEEL_SECTORS = [
    (0, "0x · Пусто"),
    (0.5, "0.5x · Половина"),
    (1.0, "1x · Возврат"),
    (1.5, "1.5x"),
    (2.0, "2x"),
    (3.0, "3x"),
    (5.0, "5x"),
    (10.0, "🔥 10x ДЖЕКПОТ"),
]


@router.message(Cmd("колесо", "wheel", "фортуна", section=S,
                    usage="колесо {ставка}", desc="Колесо фортуны (до x10)"))
async def cmd_wheel(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    await db.add_comets(uid, -bet, "gram_bet_wheel")
    msg = await message.reply("🎡 <i>Крутим барабан…</i>")
    await asyncio.sleep(2.5)

    weights = [30, 25, 20, 12, 7, 4, 1.5, 0.5]
    mult, label = random.choices(WHEEL_SECTORS, weights=weights, k=1)[0]
    is_win = mult > 1.0
    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
    kb = make_game_replay_kb("wheel", bet, uid)
    if mult > 0:
        win = int(bet * mult)
        bal = await db.add_comets(uid, win, "gram_win_wheel")
        diff = win - bet
        res = (f"🎉 <b>+{c(diff)}</b>" if diff > 0 else (f"🔸 Возврат" if diff == 0 else f"💔 −{c(-diff)}"))
        await msg.edit_text(
            f"🎡 Сектор: <b>{label}</b>\n\n"
            f"{res}\nБаланс: <b>{c(bal)}</b>{lvl_note}", reply_markup=kb)
    else:
        bal = await db.get_comets(uid)
        await msg.edit_text(
            f"🎡 Сектор: <b>{label}</b>\n\n"
            f"💔 Проигрыш −{c(bet)}\nБаланс: <b>{c(bal)}</b>{lvl_note}", reply_markup=kb)


# 6. Сапёр (Дуэль на двоих)
_sapper_duels: dict[str, dict] = {}


@router.message(Cmd("сапёр", "сапер", "sapper", section=S,
                    usage="сапёр {ставка} (ответом на сообщение)",
                    desc="Дуэль в сапёра на двоих"))
async def cmd_sapper(message: Message, bot: Bot, args: str = "", **kw):
    if not await topic_ok(message):
        return
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}

    if not message.reply_to_message or not message.reply_to_message.from_user:
        if not had_prefix and in_group:
            return
        return await message.reply("Ответьте командой на сообщение соперника!")
    target = message.reply_to_message.from_user
    if target.id == message.from_user.id or target.is_bot:
        if not had_prefix and in_group:
            return
        return await message.reply("Нельзя вызвать себя или бота.")

    bet = await take_bet(message, args, **kw)
    if bet is None:
        return

    bal_t = await db.get_comets(target.id)
    if bal_t < bet:
        if not had_prefix and in_group:
            return
        return await message.reply(f"У соперника недостаточно комет.")

    key = f"{message.chat.id}:{message.from_user.id}:{target.id}"
    _sapper_duels[key] = {
        "u1": message.from_user.id, "n1": message.from_user.first_name,
        "u2": target.id, "n2": target.first_name,
        "bet": bet, "bomb": random.randint(0, 8),
        "turn": message.from_user.id, "opened": set()
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ ПРИНЯТЬ ДУЭЛЬ", callback_data=f"sap:{key}:accept"),
        InlineKeyboardButton(text="❌ ОТКАЗ", callback_data=f"sap:{key}:decline")]])

    await message.reply(
        f"💣 <b>ДУЭЛЬ В САПЁРА</b>\n\n"
        f"{mention(message.from_user)} вызывает {mention(target)}!\n"
        f"Ставка: <b>{c(bet)}</b> с каждого.\n\n"
        f"Поле 3x3 (9 клеток). На поле 1 мина. Кто наступит — проиграл!",
        reply_markup=kb)


@router.callback_query(F.data.startswith("sap:"))
async def cb_sapper(call: CallbackQuery):
    parts = call.data.split(":")
    key = f"{parts[1]}:{parts[2]}:{parts[3]}"
    st = _sapper_duels.get(key)
    if not st:
        return await call.answer("Дуэль устарела.")

    action = parts[4]
    if action == "decline":
        if call.from_user.id != st["u2"]:
            return await call.answer("Только соперник может отклонить.")
        _sapper_duels.pop(key, None)
        return await call.message.edit_text("❌ Дуэль отклонена соперником.")

    if action == "accept":
        if call.from_user.id != st["u2"]:
            return await call.answer("Только соперник может принять!")
        b1 = await db.get_comets(st["u1"])
        b2 = await db.get_comets(st["u2"])
        if b1 < st["bet"] or b2 < st["bet"]:
            _sapper_duels.pop(key, None)
            return await call.message.edit_text("У одного из участников не хватает комет.")

        await db.add_comets(st["u1"], -st["bet"], "sap_bet")
        await db.add_comets(st["u2"], -st["bet"], "sap_bet")

        rows = []
        for r in range(3):
            row = []
            for col in range(3):
                idx = r * 3 + col
                row.append(InlineKeyboardButton(text="⬛", callback_data=f"sap:{key}:step:{idx}"))
            rows.append(row)

        await call.message.edit_text(
            f"💣 <b>САПЁР</b> · Банк: <b>{c(st['bet']*2)}</b>\n\n"
            f"Ходит: <b>{st['n1']}</b>\n"
            f"Открывайте клетки по очереди!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        return

    if action == "step":
        idx = int(parts[5])
        if call.from_user.id != st["turn"]:
            return await call.answer("Сейчас не ваш ход!", show_alert=True)
        if idx in st["opened"]:
            return await call.answer()

        st["opened"].add(idx)

        if idx == st["bomb"]:
            _sapper_duels.pop(key, None)
            loser_id = call.from_user.id
            winner_id = st["u2"] if loser_id == st["u1"] else st["u1"]
            winner_name = st["n2"] if loser_id == st["u1"] else st["n1"]
            bank = int(st["bet"] * 2 * 0.95)
            await db.add_comets(winner_id, bank, "sap_win")
            await db.add_game_xp(winner_id, 2, is_win=True)
            await db.add_game_xp(loser_id, 1, is_win=False)

            return await call.message.edit_text(
                f"💥 <b>БА-БАХ! Клетка {idx+1} оказалась миной!</b>\n\n"
                f"🏆 Победитель: <b>{winner_name}</b> (+{c(bank - st['bet'])})\n"
                f"💀 {call.from_user.first_name} подорвался на мине!")

        # Передача хода
        st["turn"] = st["u2"] if st["turn"] == st["u1"] else st["u1"]
        next_name = st["n2"] if st["turn"] == st["u2"] else st["n1"]

        rows = []
        for r in range(3):
            row = []
            for col in range(3):
                i = r * 3 + col
                if i in st["opened"]:
                    row.append(InlineKeyboardButton(text="💎", callback_data="h:noop"))
                else:
                    row.append(InlineKeyboardButton(text="⬛", callback_data=f"sap:{key}:step:{i}"))
            rows.append(row)

        await call.message.edit_text(
            f"💣 <b>САПЁР</b> · Банк: <b>{c(st['bet']*2)}</b>\n\n"
            f"Ходит: <b>{next_name}</b>\n"
            f"Открыто клеток: {len(st['opened'])}/9",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        return


# 7. Рулетка на кометы
@router.message(Cmd("рулетка кометы", section=S,
                    usage="рулетка красное 1000", desc="Рулетка на кометы"))
async def cmd_comet_roulette(message: Message, args: str = "", **kw):
    had_prefix = kw.get("had_prefix", False)
    in_group = message.chat.type in {"group", "supergroup"}
    p = (args or "").split()
    if len(p) < 2:
        if not had_prefix and in_group:
            return
        return await message.reply("Формат: <code>рулетка красное 1000</code>")
    choice = p[0].lower()
    bet = await take_bet(message, p[1], **kw)
    if bet is None:
        return
    uid = message.from_user.id
    await db.add_comets(uid, -bet, "gram_bet_roulette")
    num = random.randint(0, 36)
    red = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    color = "зеро" if num == 0 else ("красное" if num in red else "чёрное")
    mult = 0
    if choice in {"красное", "красн", "red"} and color == "красное": mult = 2
    elif choice in {"чёрное", "черное", "black"} and color == "чёрное": mult = 2
    elif choice in {"чет", "чёт", "even"} and num and num % 2 == 0: mult = 2
    elif choice in {"нечет", "нечёт", "odd"} and num % 2 == 1: mult = 2
    elif choice in {"зеро", "zero"} and num == 0: mult = 14
    elif choice.isdigit() and int(choice) == num: mult = 14

    is_win = mult > 0
    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_note = f"\n🚀 <i>Игровой уровень: <b>{lvl} LVL</b>!</i>" if lvl_up else ""
    if mult:
        win = bet * mult
        bal = await db.add_comets(uid, win, "gram_win_roulette")
        await message.reply(f"🎡 Выпало <b>{num} {color}</b> — x{mult}: +{c(win - bet)}\nБаланс: <b>{c(bal)}</b>{lvl_note}")
    else:
        bal = await db.get_comets(uid)
        await message.reply(f"🎡 Выпало <b>{num} {color}</b> — проигрыш −{c(bet)}\nБаланс: <b>{c(bal)}</b>{lvl_note}")


# ═══════════════ 8. БЛЭКДЖЕК / 21 ОЧКО ПРОТИВ МОКСИ ═══════════════
_bj_games: dict[str, dict] = {}

CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]
CARD_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def _create_deck() -> list[tuple[str, str]]:
    deck = [(r, s) for s in CARD_SUITS for r in CARD_RANKS]
    random.shuffle(deck)
    return deck


def _calc_hand_points(hand: list[tuple[str, str]]) -> int:
    pts = 0
    aces = 0
    for r, _ in hand:
        if r in ("J", "Q", "K"):
            pts += 10
        elif r == "A":
            pts += 11
            aces += 1
        else:
            pts += int(r)
    while pts > 21 and aces > 0:
        pts -= 10
        aces -= 1
    return pts


def _fmt_hand(hand: list[tuple[str, str]], hide_second: bool = False) -> str:
    if hide_second and len(hand) >= 2:
        return f"[ {hand[0][1]} {hand[0][0]} ] [ 🂠 ??? ] (?? очков)"
    cards_str = " ".join(f"[ {s} {r} ]" for r, s in hand)
    pts = _calc_hand_points(hand)
    return f"{cards_str} (<b>{pts}</b> очков)"


def _bj_kb(key: str, can_double: bool = False) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text="🃏 Взять карту", callback_data=f"bj:hit:{key}"),
        InlineKeyboardButton(text="🛑 Хватит", callback_data=f"bj:stand:{key}"),
    ]
    if can_double:
        row1.append(InlineKeyboardButton(text="💥 2x Удвоить", callback_data=f"bj:double:{key}"))
    return InlineKeyboardMarkup(inline_keyboard=[row1])


async def _finish_bj_game(call: CallbackQuery, key: str, st: dict, outcome: str):
    _bj_games.pop(key, None)
    uid = st["uid"]
    bet = st["bet"]
    chat_id = st["chat_id"]

    is_win = False
    payout = 0
    res_title = ""

    if outcome == "blackjack":
        is_win = True
        payout = int(bet * 2.5)  # Натуральный блэкджек x2.5
        res_title = "🎉 💥 <b>НАТУРАЛЬНЫЙ БЛЭКДЖЕК (21)! x2.5!</b> 💥 🎉"
    elif outcome == "win":
        is_win = True
        payout = bet * 2
        res_title = "🎉 <b>ВЫ ПОБЕДИЛИ МОКСИ! +x2!</b> 🎉"
    elif outcome == "draw":
        is_win = False
        payout = bet
        res_title = "🤝 <b>НИЧЬЯ (PUSH)!</b> Ставка возвращена."
    elif outcome == "bust":
        is_win = False
        payout = 0
        res_title = "💥 <b>ПЕРЕБОР (>21)! ВЫ ПРОИГРАЛИ.</b> 💔"
    elif outcome == "lose":
        is_win = False
        payout = 0
        res_title = "💔 <b>МОКСИ ВЫИГРАЛА ЭТУ РАЗДАЧУ!</b>"

    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_note = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""

    if payout > 0:
        new_bal = await db.add_comets(uid, payout, "bj_payout")
        profit = payout - bet
        if profit >= 10_000 or outcome == "blackjack":
            try:
                await db.record_big_win(uid, call.from_user.first_name, chat_id, "Блэкджек 🃏", bet, payout)
            except Exception:
                pass
        profit_str = f"+{c(profit)}" if profit > 0 else "0 🪙 (возврат)"
        gain_line = f"💰 <b>Выплата:</b> <b>{profit_str}</b>\n"
    else:
        new_bal = await db.get_comets(uid)
        gain_line = f"💸 <b>Потеряно:</b> <b>−{c(bet)}</b>\n"

    p_hand_str = _fmt_hand(st["player"], hide_second=False)
    d_hand_str = _fmt_hand(st["dealer"], hide_second=False)

    text = (
        f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО ПРОТИВ МОКСИ</b> 🍸\n"
        f"✦ ══ • ⊰ ♠️ ♥️ ♦️ ♣️ ⊱ • ══ ✦\n\n"
        f"{res_title}\n\n"
        f"👤 <b>Ваши карты:</b>\n{p_hand_str}\n\n"
        f"💋 <b>Карты Мокси (дилера):</b>\n{d_hand_str}\n\n"
        f"{gain_line}"
        f"💰 <b>Ваш баланс:</b> <b>{c(new_bal)}</b>{lvl_note}"
    )

    replay_kb = make_game_replay_kb("bj", bet, uid)
    try:
        await call.message.edit_text(text, reply_markup=replay_kb)
    except Exception:
        await call.message.reply(text, reply_markup=replay_kb)


async def start_quick_blackjack(call: CallbackQuery, bet: int):
    """Быстрый старт блэкджека по нажатию инлайн-кнопки реплея."""
    uid = call.from_user.id
    chat_id = call.message.chat.id
    bal = await db.get_comets(uid)
    if bal < bet:
        return await call.answer(f"Недостаточно монет! Баланс: {c(bal)}", show_alert=True)

    await db.add_comets(uid, -bet, "bj_bet")
    if call.message.chat.type in {"group", "supergroup"}:
        try:
            await db.add_to_chat_jackpot(chat_id, int(bet * 0.02))
        except Exception:
            pass

    deck = _create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    key = f"{chat_id}:{uid}:{int(time.time() * 1000)}"
    st = {
        "bet": bet,
        "uid": uid,
        "chat_id": chat_id,
        "deck": deck,
        "player": player_hand,
        "dealer": dealer_hand,
        "can_double": True
    }
    _bj_games[key] = st

    p_pts = _calc_hand_points(player_hand)
    d_pts = _calc_hand_points(dealer_hand)

    if p_pts == 21:
        if d_pts == 21:
            _bj_games.pop(key, None)
            new_bal = await db.add_comets(uid, bet, "bj_refund")
            p_hand_str = _fmt_hand(player_hand, hide_second=False)
            d_hand_str = _fmt_hand(dealer_hand, hide_second=False)
            text = (
                f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО</b> 🍸\n\n"
                f"🤝 <b>ДВОЙНОЙ БЛЭКДЖЕК! НИЧЬЯ (PUSH)!</b>\n\n"
                f"👤 <b>Ваши карты:</b> {p_hand_str}\n"
                f"💋 <b>Карты Мокси:</b> {d_hand_str}\n\n"
                f"Ставка возвращена: <b>{c(bet)}</b>\nБаланс: <b>{c(new_bal)}</b>"
            )
            return await call.message.reply(text, reply_markup=make_game_replay_kb("bj", bet, uid))
        else:
            _bj_games.pop(key, None)
            payout = int(bet * 2.5)
            new_bal = await db.add_comets(uid, payout, "bj_natural_win")
            try:
                await db.record_big_win(uid, call.from_user.first_name, chat_id, "Блэкджек 🃏", bet, payout)
            except Exception:
                pass
            p_hand_str = _fmt_hand(player_hand, hide_second=False)
            d_hand_str = _fmt_hand(dealer_hand, hide_second=False)
            text = (
                f"🃏 💥 <b>НАТУРАЛЬНЫЙ БЛЭКДЖЕК! x2.5!</b> 💥 🍸\n\n"
                f"👤 <b>Ваши карты:</b> {p_hand_str}\n"
                f"💋 <b>Карты Мокси:</b> {d_hand_str}\n\n"
                f"🎉 Выигрыш: <b>+{c(payout - bet)}</b>\nБаланс: <b>{c(new_bal)}</b>"
            )
            return await call.message.reply(text, reply_markup=make_game_replay_kb("bj", bet, uid))

    p_hand_str = _fmt_hand(player_hand, hide_second=False)
    d_hand_str = _fmt_hand(dealer_hand, hide_second=True)

    text = (
        f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО ПРОТИВ МОКСИ</b> 🍸\n"
        f"✦ ══ • ⊰ ♠️ ♥️ ♦️ ♣️ ⊱ • ══ ✦\n\n"
        f"👤 <b>Ваши карты:</b>\n{p_hand_str}\n\n"
        f"💋 <b>Карты Мокси (дилера):</b>\n{d_hand_str}\n\n"
        f"💰 Ставка: <b>{c(bet)}</b>\n"
        f"👉 <i>Сделайте ход с помощью кнопок:</i>"
    )
    can_double = (await db.get_comets(uid)) >= bet
    await call.message.reply(text, reply_markup=_bj_kb(key, can_double=can_double))


@router.message(Cmd("блэкджек", "блекджек", "бд", "21", "очко", "blackjack", "bj", section=S,
                    usage="бд {ставка}", desc="Карточный блэкджек (21 очко) против Мокси · Натуральный x2.5"))
async def cmd_blackjack(message: Message, args: str = "", **kw):
    bet = await take_bet(message, args, **kw)
    if bet is None:
        return
    uid = message.from_user.id
    chat_id = message.chat.id

    # Списываем ставку
    await db.add_comets(uid, -bet, "bj_bet")

    # 2% в джекпот чата
    if message.chat.type in {"group", "supergroup"}:
        try:
            await db.add_to_chat_jackpot(chat_id, int(bet * 0.02))
        except Exception:
            pass

    deck = _create_deck()
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    key = f"{chat_id}:{uid}:{int(time.time() * 1000)}"
    st = {
        "bet": bet,
        "uid": uid,
        "chat_id": chat_id,
        "deck": deck,
        "player": player_hand,
        "dealer": dealer_hand,
        "can_double": True
    }
    _bj_games[key] = st

    p_pts = _calc_hand_points(player_hand)
    d_pts = _calc_hand_points(dealer_hand)

    if p_pts == 21:
        if d_pts == 21:
            _bj_games.pop(key, None)
            new_bal = await db.add_comets(uid, bet, "bj_refund")
            p_hand_str = _fmt_hand(player_hand, hide_second=False)
            d_hand_str = _fmt_hand(dealer_hand, hide_second=False)
            text = (
                f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО</b> 🍸\n\n"
                f"🤝 <b>ДВОЙНОЙ БЛЭКДЖЕК! НИЧЬЯ (PUSH)!</b>\n\n"
                f"👤 <b>Ваши карты:</b> {p_hand_str}\n"
                f"💋 <b>Карты Мокси:</b> {d_hand_str}\n\n"
                f"Ставка возвращена: <b>{c(bet)}</b>\nБаланс: <b>{c(new_bal)}</b>"
            )
            return await message.reply(text, reply_markup=make_game_replay_kb("bj", bet, uid))
        else:
            _bj_games.pop(key, None)
            payout = int(bet * 2.5)
            new_bal = await db.add_comets(uid, payout, "bj_natural_win")
            try:
                await db.record_big_win(uid, message.from_user.first_name, chat_id, "Блэкджек 🃏", bet, payout)
            except Exception:
                pass
            p_hand_str = _fmt_hand(player_hand, hide_second=False)
            d_hand_str = _fmt_hand(dealer_hand, hide_second=False)
            text = (
                f"🃏 💥 <b>НАТУРАЛЬНЫЙ БЛЭКДЖЕК! x2.5!</b> 💥 🍸\n\n"
                f"👤 <b>Ваши карты:</b> {p_hand_str}\n"
                f"💋 <b>Карты Мокси:</b> {d_hand_str}\n\n"
                f"🎉 Выигрыш: <b>+{c(payout - bet)}</b>\nБаланс: <b>{c(new_bal)}</b>"
            )
            return await message.reply(text, reply_markup=make_game_replay_kb("bj", bet, uid))

    p_hand_str = _fmt_hand(player_hand, hide_second=False)
    d_hand_str = _fmt_hand(dealer_hand, hide_second=True)

    text = (
        f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО ПРОТИВ МОКСИ</b> 🍸\n"
        f"✦ ══ • ⊰ ♠️ ♥️ ♦️ ♣️ ⊱ • ══ ✦\n\n"
        f"👤 <b>Ваши карты:</b>\n{p_hand_str}\n\n"
        f"💋 <b>Карты Мокси (дилера):</b>\n{d_hand_str}\n\n"
        f"💰 Ставка: <b>{c(bet)}</b>\n"
        f"👉 <i>Сделайте ход с помощью кнопок:</i>"
    )
    can_double = (await db.get_comets(uid)) >= bet
    await message.reply(text, reply_markup=_bj_kb(key, can_double=can_double))


@router.callback_query(F.data.startswith("bj:"))
async def cb_bj_action(call: CallbackQuery):
    parts = call.data.split(":")
    act = parts[1]
    key = f"{parts[2]}:{parts[3]}:{parts[4]}"
    st = _bj_games.get(key)
    if not st:
        return await call.answer("Эта партия уже завершена или устарела.", show_alert=True)

    if call.from_user.id != st["uid"]:
        return await call.answer("Это не ваша партия! Напишите бд [ставка] для своей игры 😉", show_alert=True)

    if act == "hit":
        st["can_double"] = False
        st["player"].append(st["deck"].pop())
        pts = _calc_hand_points(st["player"])

        if pts > 21:
            await call.answer("Перебор!")
            return await _finish_bj_game(call, key, st, "bust")
        elif pts == 21:
            await call.answer("21 очко!")
            while _calc_hand_points(st["dealer"]) < 17:
                st["dealer"].append(st["deck"].pop())
            d_pts = _calc_hand_points(st["dealer"])
            if d_pts > 21 or 21 > d_pts:
                return await _finish_bj_game(call, key, st, "win")
            elif d_pts == 21:
                return await _finish_bj_game(call, key, st, "draw")
            else:
                return await _finish_bj_game(call, key, st, "lose")

        p_hand_str = _fmt_hand(st["player"], hide_second=False)
        d_hand_str = _fmt_hand(st["dealer"], hide_second=True)
        text = (
            f"🃏 <b>БЛЭКДЖЕК / 21 ОЧКО ПРОТИВ МОКСИ</b> 🍸\n"
            f"✦ ══ • ⊰ ♠️ ♥️ ♦️ ♣️ ⊱ • ══ ✦\n\n"
            f"👤 <b>Ваши карты:</b>\n{p_hand_str}\n\n"
            f"💋 <b>Карты Мокси (дилера):</b>\n{d_hand_str}\n\n"
            f"💰 Ставка: <b>{c(st['bet'])}</b>\n"
            f"👉 <i>Сделайте ход:</i>"
        )
        await call.answer(f"Счёт: {pts}")
        try:
            await call.message.edit_text(text, reply_markup=_bj_kb(key, can_double=False))
        except Exception:
            pass
        return

    elif act == "double":
        bal = await db.get_comets(st["uid"])
        if bal < st["bet"]:
            return await call.answer("Недостаточно монет для удвоения ставки!", show_alert=True)
        await db.add_comets(st["uid"], -st["bet"], "bj_double_bet")
        st["bet"] *= 2
        st["player"].append(st["deck"].pop())
        pts = _calc_hand_points(st["player"])

        if pts > 21:
            await call.answer("Перебор!")
            return await _finish_bj_game(call, key, st, "bust")

        while _calc_hand_points(st["dealer"]) < 17:
            st["dealer"].append(st["deck"].pop())
        d_pts = _calc_hand_points(st["dealer"])

        if d_pts > 21 or pts > d_pts:
            return await _finish_bj_game(call, key, st, "win")
        elif pts == d_pts:
            return await _finish_bj_game(call, key, st, "draw")
        else:
            return await _finish_bj_game(call, key, st, "lose")

    elif act == "stand":
        await call.answer("Ход дилера...")
        pts = _calc_hand_points(st["player"])

        while _calc_hand_points(st["dealer"]) < 17:
            st["dealer"].append(st["deck"].pop())
        d_pts = _calc_hand_points(st["dealer"])

        if d_pts > 21:
            return await _finish_bj_game(call, key, st, "win")
        elif pts > d_pts:
            return await _finish_bj_game(call, key, st, "win")
        elif pts == d_pts:
            return await _finish_bj_game(call, key, st, "draw")
        else:
            return await _finish_bj_game(call, key, st, "lose")


# ═══════════════ СКАЧКИ НА ИППОДРОМЕ ═══════════════
HORSES = [
    {"id": 1, "name": "⚡ Молния", "odds": 2.2, "weight": 42, "desc": "Фаворит трека", "icon": "⚡"},
    {"id": 2, "name": "🛡 Буцефал", "odds": 3.5, "weight": 26, "desc": "Могучий тяжеловес", "icon": "🛡"},
    {"id": 3, "name": "🪽 Пегас", "odds": 5.0, "weight": 18, "desc": "Стремительный скакун", "icon": "🪽"},
    {"id": 4, "name": "🌪 Торнадо", "odds": 8.0, "weight": 10, "desc": "Буйный мустанг", "icon": "🌪"},
    {"id": 5, "name": "💨 Ветерок", "odds": 15.0, "weight": 4, "desc": "Дерзкий аутсайдер", "icon": "💨"},
]


def _horse_menu_kb(bet: int = 1000) -> InlineKeyboardMarkup:
    rows = []
    rows.append([
        InlineKeyboardButton(text="1️⃣ ⚡ Молния (x2.2)", callback_data=f"horse_pick:1:{bet}"),
        InlineKeyboardButton(text="2️⃣ 🛡 Буцефал (x3.5)", callback_data=f"horse_pick:2:{bet}"),
    ])
    rows.append([
        InlineKeyboardButton(text="3️⃣ 🪽 Пегас (x5.0)", callback_data=f"horse_pick:3:{bet}"),
        InlineKeyboardButton(text="4️⃣ 🌪 Торнадо (x8.0)", callback_data=f"horse_pick:4:{bet}"),
    ])
    rows.append([
        InlineKeyboardButton(text="5️⃣ 💨 Ветерок (x15.0 - ДЖЕКПОТ!)", callback_data=f"horse_pick:5:{bet}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _run_race_animation(msg: Message, user_name: str, chosen_h: dict, bet: int, uid: int, chat_id: int):
    # Кадр 1: Старт
    f1 = (
        f"🏇 <b>БОЛЬШИЕ СКАЧКИ НА ИППОДРОМЕ МОКСИ!</b> 🏇\n"
        f"✦ ══ • ⊰ ⚡ 🛡 🪽 🌪 💨 ⊱ • ══ ✦\n"
        f"👤 Жокей: <b>{html.escape(user_name)}</b>\n"
        f"🎯 Ставка: <b>{c(bet)}</b> на <b>{chosen_h['name']} (x{chosen_h['odds']})</b>\n\n"
        f"🚦 <i>Ворота распахнуты! Скакуны рванули вперед!</i>\n\n"
        f"1. ⚡ Молния:    🟩🟩🟩🏇─────────────\n"
        f"2. 🛡 Буцефал:   🟩🟩🏇───────────────\n"
        f"3. 🪽 Пегас:     🟩🟩🟩🟩🏇───────────\n"
        f"4. 🌪 Торнадо:   🟩🟩🏇───────────────\n"
        f"5. 💨 Ветерок:   🟩🏇─────────────────\n"
    )
    try:
        await msg.edit_text(f1)
    except Exception:
        pass

    await asyncio.sleep(1.2)

    # Кадр 2: Борьба на вираже
    f2 = (
        f"🏇 <b>ФИНИШНАЯ ПРЯМАЯ!</b> 🔥\n"
        f"✦ ══ • ⊰ ⚡ 🛡 🪽 🌪 💨 ⊱ • ══ ✦\n"
        f"👤 Жокей: <b>{html.escape(user_name)}</b>\n"
        f"🎯 Ставка: <b>{c(bet)}</b> на <b>{chosen_h['name']} (x{chosen_h['odds']})</b>\n\n"
        f"🔥 <i>Трибуны ревут! Кони идут ноздря в ноздрю!</i>\n\n"
        f"1. ⚡ Молния:    🟩🟩🟩🟩🟩🟩🟩🏇─────\n"
        f"2. 🛡 Буцефал:   🟩🟩🟩🟩🟩🟩🏇───────\n"
        f"3. 🪽 Пегас:     🟩🟩🟩🟩🟩🟩🟩🟩🏇───\n"
        f"4. 🌪 Торнадо:   🟩🟩🟩🟩🟩🏇─────────\n"
        f"5. 💨 Ветерок:   🟩🟩🟩🟩🟩🟩🟩🟩🟩🏇─\n"
    )
    try:
        await msg.edit_text(f2)
    except Exception:
        pass

    await asyncio.sleep(1.2)

    # Определение победителя по весам
    weights = [h["weight"] for h in HORSES]
    winner = random.choices(HORSES, weights=weights, k=1)[0]
    is_win = (winner["id"] == chosen_h["id"])

    lvl, lvl_up = await db.add_game_xp(uid, 1, is_win=is_win)
    lvl_tag = f"\n🚀 <i>Игровой уровень повышен до <b>{lvl} LVL</b>!</i>" if lvl_up else ""

    kb = make_game_replay_kb("race", bet, uid, str(chosen_h["id"]))

    if is_win:
        win_amt = int(bet * winner["odds"])
        profit = win_amt - bet
        new_bal = await db.add_comets(uid, win_amt, "horse_win")
        if profit >= 5000:
            await record_big_win(chat_id, uid, user_name, f"🏇 Скачки ({winner['name']})", profit)

        f3 = (
            f"🏆 <b>ФИНИШ! ПОБЕДИТЕЛЬ: {winner['name']} (x{winner['odds']})!</b> 🏆\n"
            f"✦ ══ • ⊰ 🥇 🏇 ✨ ⊱ • ══ ✦\n\n"
            f"🎉 <b>ПОБЕДА! Ваш скакун пересёк черту первым!</b>\n"
            f"💰 Выигрыш: <b>+{c(win_amt)}</b> <i>(чистая прибыль: +{c(profit)})</i>\n"
            f"🪙 Ваш баланс: <b>{c(new_bal)}</b>{lvl_tag}"
        )
    else:
        bal = await db.get_comets(uid)
        f3 = (
            f"🏆 <b>ФИНИШ! ПОБЕДИТЕЛЬ: {winner['name']} (x{winner['odds']})!</b> 🏆\n"
            f"✦ ══ • ⊰ 🏁 🏇 🥀 ⊱ • ══ ✦\n\n"
            f"💔 <b>Увы, {chosen_h['name']} не пришёл первым...</b>\n"
            f"Потери: <b>−{c(bet)}</b>\n"
            f"🪙 Ваш баланс: <b>{c(bal)}</b>{lvl_tag}"
        )

    try:
        await msg.edit_text(f3, reply_markup=kb)
    except Exception:
        await msg.reply(f3, reply_markup=kb)


@router.message(Cmd("скачки", "ипподром", "лошади", "заезд", "кони", section=S,
                    usage="скачки {номер} {ставка}", desc="Скачки на ипподроме (до x15)"))
async def cmd_horse_race(message: Message, args: str = "", **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    await _ensure_start(uid)

    parts = (args or "").strip().split()
    if not parts or not parts[0].isdigit() or int(parts[0]) not in {1, 2, 3, 4, 5}:
        text = (
            f"🏇 <b>БОЛЬШИЕ СКАЧКИ НА ИППОДРОМЕ МОКСИ!</b> 🏇\n"
            f"✦ ══ • ⊰ 🏆 🏇 ⚡ 🛡 🪽 🌪 💨 ⊱ • ══ ✦\n\n"
            f"Добро пожаловать на главную арену королевских скачек!\n"
            f"Выберите своего скакуна и сорвите огромный куш:\n\n"
            f"1️⃣ ⚡ <b>Молния</b> — кэф <code>x2.20</code> (Фаворит, шанс 42%)\n"
            f"2️⃣ 🛡 <b>Буцефал</b> — кэф <code>x3.50</code> (Могучий скакун, шанс 26%)\n"
            f"3️⃣ 🪽 <b>Пегас</b> — кэф <code>x5.00</code> (Стремительный, шанс 18%)\n"
            f"4️⃣ 🌪 <b>Торнадо</b> — кэф <code>x8.00</code> (Буйный мустанг, шанс 10%)\n"
            f"5️⃣ 💨 <b>Ветерок</b> — кэф <code>x15.00</code> (Дерзкий аутсайдер, шанс 4%!)\n\n"
            f"💡 <i>Сделайте ставку командой:</i> <code>скачки 1 1000</code>\n"
            f"<i>или выберите скакуна со ставкой 1 000 🪙 кнопкой:</i>"
        )
        return await message.reply(text, reply_markup=_horse_menu_kb(1000))

    horse_id = int(parts[0])
    chosen_h = next(h for h in HORSES if h["id"] == horse_id)
    bet_raw = " ".join(parts[1:]) if len(parts) > 1 else "1000"

    bet = await take_bet(message, bet_raw, **kw)
    if bet is None:
        return

    await db.add_comets(uid, -bet, "horse_bet")
    init_msg = await message.reply(
        f"🏇 <b>Ставка принята!</b>\n"
        f"Вы поставили <b>{c(bet)}</b> на <b>{chosen_h['name']}</b>!\n"
        f"Подготовка к старту..."
    )
    await _run_race_animation(init_msg, message.from_user.first_name, chosen_h, bet, uid, message.chat.id)


@router.callback_query(F.data.startswith("horse_pick:"))
async def cb_horse_pick(call: CallbackQuery):
    parts = call.data.split(":")
    horse_id = int(parts[1])
    bet = int(parts[2])
    uid = call.from_user.id

    if not await topic_ok(call.message):
        return await call.answer("Казино отключено в этом чате или теме.", show_alert=True)

    bal = await db.get_comets(uid)
    if bal < bet:
        return await call.answer(f"Недостаточно монет! Нужно {c(bet)}, у вас: {c(bal)}", show_alert=True)

    chosen_h = next((h for h in HORSES if h["id"] == horse_id), HORSES[0])
    await db.add_comets(uid, -bet, "horse_bet")
    await call.answer(f"Ставка {c(bet)} на {chosen_h['name']}!")

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await _run_race_animation(call.message, call.from_user.first_name, chosen_h, bet, uid, call.message.chat.id)


async def start_quick_race(call: CallbackQuery, bet: int, horse_idx: int):
    uid = call.from_user.id
    bal = await db.get_comets(uid)
    if bal < bet:
        return await call.answer(f"Недостаточно монет! Нужно {c(bet)}, у вас: {c(bal)}", show_alert=True)

    chosen_h = next((h for h in HORSES if h["id"] == horse_idx), HORSES[0])
    await db.add_comets(uid, -bet, "horse_bet")
    await call.answer(f"🏇 Скачки на {chosen_h['name']}!")

    msg = await call.message.reply(f"🏇 Новый заезд! Ставка <b>{c(bet)}</b> на <b>{chosen_h['name']}</b>...")
    await _run_race_animation(msg, call.from_user.first_name, chosen_h, bet, uid, call.message.chat.id)


# ═══════════════ АДМИНСКИЕ КОМАНДЫ ДЛЯ ВАЛЮТЫ ═══════════════
@router.message(Cmd("монеты выдать", "выдать монеты", "начислить монеты", "coin give", "coins give", "выдать коины", "выдать граммы", "выдать кометы", "дать монеты", "дать коины", "кометы выдать", "выдать", "начислить", "p give", section=S, rank=6,
                    usage="выдать {ссылка} {сумма}",
                    desc="Начислить валюту 🪙 (техадмин / 6+ ранг)"))
async def cmd_give_admin(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        # Если цель не указана — действие к себе
        uid, name = message.from_user.id, message.from_user.first_name
        rest = args
    amount = parse_amount(rest, 10**14, 1)
    if not amount:
        return await message.reply("Укажите сумму: <code>выдать @user 50000</code>")
    bal = await db.add_balance(uid, amount, "admin_add", str(message.from_user.id))
    await message.reply(f"✅ {mention_id(uid, name)} получил <b>+{c(amount)}</b>\n"
                        f"Баланс: <b>{c(bal)}</b>")


@router.message(Cmd("выдать бизнес", "дать бизнес", "бизнес выдать", "выдать предприятие", section=S, rank=6,
                    usage="выдать бизнес {ссылка} {название} [кол-во]",
                    desc="Выдать предприятие игроку (техадмин / 6+ ранг)"))
async def cmd_give_business(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
        rest = args
    parts = (rest or "").strip().split()
    if not parts:
        return await message.reply("Использование: <code>выдать бизнес @user ферма 1</code>")
    count = 1
    if parts[-1].isdigit():
        count = max(1, min(1000, int(parts[-1])))
        name_q = " ".join(parts[:-1])
    else:
        name_q = " ".join(parts)
    biz_key, info = find_business_by_alias(name_q)
    if not biz_key:
        return await message.reply("❌ Предприятие не найдено. Напишите <code>бизнесы</code>.")
    new_count = await db.change_user_business(uid, biz_key, count)
    try:
        core_backup.schedule_quick_backup(bot)
    except Exception:
        pass
    await message.reply(f"✅ {mention_id(uid, name)} выдано: {info['emoji']} <b>{info['name']}</b> × {count} шт. (всего: <b>{new_count} шт.</b>)")


@router.message(Cmd("монеты сет", "монеты set", "сет монет", "установить монеты", "coin set", "set coins", "кометы сет", "сет", "set", "установить", "p set", section=S, rank=6,
                    usage="сет {ссылка} {сумма}",
                    desc="Установить точный баланс (техадмин / 6+ ранг)"))
async def cmd_set_admin(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
        rest = args
    amount = parse_amount(rest, 10**14, 0)
    if amount is None or amount < 0:
        return await message.reply("Укажите сумму: <code>сет @user 100000</code>")
    bal = await db.set_balance(uid, amount)
    await message.reply(f"✅ Баланс {mention_id(uid, name)} установлен на <b>{c(bal)}</b>")


@router.message(Cmd("монеты снять", "снять монеты", "забрать монеты", "снять коины", "забрать коины", "кометы снять", "снять", "забрать", section=S, rank=6,
                    usage="снять {ссылка} {сумма}",
                    desc="Снять валюту 🪙 (техадмин / 6+ ранг)"))
async def cmd_take_admin(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 6):
        return
    uid, name, rest = await resolve_target(message, args, bot)
    if not uid:
        uid, name = message.from_user.id, message.from_user.first_name
        rest = args
    amount = parse_amount(rest, 10**14, 1)
    if not amount:
        return await message.reply("Укажите сумму: <code>снять @user 50000</code>")
    bal = await db.add_balance(uid, -amount, "admin_take", str(message.from_user.id))
    await message.reply(f"✅ У {mention_id(uid, name)} списано <b>−{c(amount)}</b>\n"
                        f"Баланс: <b>{c(bal)}</b>")


# ═══════════════ ПРИВЯЗКА ТЕМЫ ДЛЯ ИГР ═══════════════
@router.message(Cmd("тема игр", "тема монет", "тема коинов", "тема казино", "тема казик", "тема граммов", "тема комет",
                    "+тема игр", "+тема монет", "+тема казино", "+тема казик", section=S, rank=4,
                    usage="тема игр [ссылка]",
                    desc="Тема, где работают игры, казино и валюта"))
async def cmd_gram_topic(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 4):
        return

    if not getattr(message.chat, "is_forum", False):
        return await message.reply(
            "⚠️ <b>Привязка тем доступна только в группах с включенными Темами (Форум)!</b>\n\n"
            "В обычном чате без тем игры и казино работают прямо в основном чате.\n"
            "Чтобы включить темы, откройте: <i>Настройки группы → Темы</i>."
        )

    a = (args or "").strip()

    if a.lower() in {"сброс", "убрать", "выкл", "off"}:
        await db.set_setting(message.chat.id, "gram_topic", "0")
        return await message.reply("✅ Привязка снята — игры работают везде.")

    import re as _re
    tid = 0
    m = _re.search(r"t\.me/c/\d+/(\d+)", a)
    if m:
        tid = int(m.group(1))
    elif a.isdigit():
        tid = int(a)
    elif not a:
        tid = _tid(message)

    if not tid:
        cur = await get_gram_topic(message.chat.id)
        cur_txt = (f"Сейчас: {_tlink(message.chat.id, cur)}" if cur else "Сейчас: не задана")
        return await message.reply(
            f"🪙 <b>Тема для игр и валюты</b>\n\n{cur_txt}\n\n"
            f"Установить — напишите команду <b>в нужной теме</b>:\n"
            f"<code>тема игр</code>\n\n"
            f"Или ссылкой:\n<code>тема игр https://t.me/c/123456/789</code>\n\n"
            f"Снять: <code>тема игр сброс</code>",
            disable_web_page_preview=True)

    await db.set_setting(message.chat.id, "gram_topic", str(tid))
    await message.reply(
        f"✅ <b>Тема для игр и валюты установлена</b>\n\n🪙 {_tlink(message.chat.id, tid)}\n\n"
        f"Все игры и команды валюты теперь работают <b>только там</b>.",
        disable_web_page_preview=True)


# ═══════════════ ИНФОРМАЦИЯ О ЕДИНОЙ ВАЛЮТЕ ═══════════════
@router.message(Cmd("обмен", "обменять", "курс", "exchange", section=S,
                    usage="обмен",
                    desc="Информация о единой валюте бота"))
async def cmd_exchange(message: Message, **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    await _ensure_start(uid)
    bal = await db.get_balance(uid)
    await message.reply(
        f"ℹ️ В боте действует <b>единая валюта {COIN}</b>!\n\n"
        f"💰 Ваш баланс: <b>{c(bal)}</b>\n\n"
        f"Обмен не требуется — все игры, предприятия, переводы и покупки работают напрямую с вашим единым балансом 🪙.\n\n"
        f"💡 <i>Открыть рынок: <code>бизнесы</code> · Игры: <code>игры</code> · Баланс: <code>б</code></i>")


# ═══════════════ ВЫПКА (VIP) ЗА ВАЛЮТУ ═══════════════
VIP_PRICE = 100_000
VIP_DAYS = 5


@router.message(Cmd("выпка", "купить выпку", "вypka", section=S,
                    usage="выпка",
                    desc=f"Купить выпку на {VIP_DAYS} дней за {c(VIP_PRICE)}"))
async def cmd_vip(message: Message, **kw):
    if not await topic_ok(message):
        return
    uid = message.from_user.id
    await _ensure_start(uid)
    row = await db.fetchone("SELECT until FROM vip WHERE user_id=?", (uid,))
    active = row and row["until"] > time.time()
    left = ""
    if active:
        d = int((row["until"] - time.time()) // 86400)
        h = int(((row["until"] - time.time()) % 86400) // 3600)
        left = f"\n\n✅ <b>Выпка активна</b> ещё {d} д {h} ч"
    bal = await db.get_balance(uid)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"👑 Купить за {c(VIP_PRICE)}",
                             callback_data="vipbuy")]])
    await message.reply(
        f"👑 <b>ВЫПКА</b> — {VIP_DAYS} дней за <b>{c(VIP_PRICE)}</b>\n\n"
        f"Что даёт:\n"
        f"• ×2 к ежедневным бонусам\n"
        f"• Бонусы к работе и защита от воров\n"
        f"• 👑 значок в профиле\n\n"
        f"Ваш баланс: <b>{c(bal)}</b>{left}",
        reply_markup=kb)


@router.callback_query(F.data == "vipbuy")
async def cb_vip(call: CallbackQuery):
    uid = call.from_user.id
    bal = await db.get_balance(uid)
    if bal < VIP_PRICE:
        return await call.answer(
            f"Недостаточно средств.\nНужно {c(VIP_PRICE)}, у вас {c(bal)}",
            show_alert=True)
    await db.add_balance(uid, -VIP_PRICE, "vip_buy")
    row = await db.fetchone("SELECT until FROM vip WHERE user_id=?", (uid,))
    base = max(int(time.time()), int(row["until"]) if row else 0)
    until = base + VIP_DAYS * 86400
    await db.execute(
        "INSERT INTO vip (user_id, until, level) VALUES (?,?,1) "
        "ON CONFLICT(user_id) DO UPDATE SET until=excluded.until", (uid, until))
    nu = await db.get_balance(uid)
    try:
        await call.message.edit_text(
            f"👑 <b>Выпка куплена!</b>\n\n"
            f"Срок: <b>{VIP_DAYS} дней</b>\n"
            f"Списано: <b>−{c(VIP_PRICE)}</b>\n"
            f"Баланс: <b>{c(nu)}</b>")
    except Exception:
        pass
    await call.answer("👑 Выпка активирована!")


# ═══════════════ ВЫДАЧА ВЫПКИ АДМИНОМ ═══════════════
@router.message(Cmd("выдать выпку", "дать выпку", "+выпка", "выпку",
                    "начислить выпку", section=S, rank=4,
                    usage="выдать выпку @ник 7 дней",
                    desc="Выдать участнику выпку бесплатно (ранг 4+)"))
async def cmd_vip_give(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 4):
        return

    a = (args or "").strip()
    if not a and not message.reply_to_message:
        return await message.reply(
            "👑 <b>Выдать выпку</b>\n\n"
            "<code>выдать выпку @ник 7 дней</code>\n"
            "<code>выдать выпку @ник 1 месяц</code>\n"
            "<code>выдать выпку @ник навсегда</code>\n"
            "<code>выдать выпку @ник</code> — на 5 дней\n\n"
            "Или ответом на сообщение человека.\n\n"
            "Снять: <code>снять выпку @ник</code>\n"
            "Список: <code>кто с выпкой</code>")

    uid, name, rest = await resolve_target(message, a, bot)
    if not uid:
        return await message.reply(
            "🤔 Кому выдать? Укажите <code>@ник</code> "
            "или ответьте на сообщение человека.")

    rest = (rest or "").strip().lower()
    forever = rest in {"навсегда", "вечно", "бессрочно", "forever"}
    if forever:
        secs = 0
    else:
        secs, _ = parse_period(rest)
        if not secs:
            secs = VIP_DAYS * 86400

    row = await db.fetchone("SELECT until FROM vip WHERE user_id=?", (uid,))
    had = row and int(row["until"] or 0) > int(time.time())
    if forever:
        until = 4102444800
    else:
        base = max(int(time.time()), int(row["until"]) if row else 0)
        until = base + secs

    await db.execute(
        "INSERT INTO vip (user_id, until, level) VALUES (?,?,1) "
        "ON CONFLICT(user_id) DO UPDATE SET until=excluded.until", (uid, until))

    term = "навсегда" if forever else human_period(secs)
    when = ("" if forever else
            f"\n📅 До: <b>{time.strftime('%d.%m.%Y %H:%M', time.localtime(until))}</b>")
    await message.reply(
        f"👑 <b>Выпка выдана</b>\n"
        f"👤 {mention_id(uid, name)}\n"
        f"⏱ Срок: <b>{term}</b>"
        f"{' <i>(продлена)</i>' if had and not forever else ''}"
        f"{when}\n"
        f"🎁 Бесплатно, от {mention_id(message.from_user.id, message.from_user.first_name)}")

    try:
        await bot.send_message(
            uid,
            f"👑 <b>Вам выдали выпку!</b>\n\n"
            f"⏱ Срок: <b>{term}</b>{when}\n\n"
            f"Что даёт: удвоенный бонус, приоритет в играх "
            f"и значок 👑 в профиле.")
    except Exception:
        pass


@router.message(Cmd("снять выпку", "убрать выпку", "-выпка", "забрать выпку",
                    section=S, rank=4, usage="снять выпку @ник",
                    desc="Снять выпку у участника (ранг 4+)"))
async def cmd_vip_take(message: Message, bot: Bot, args: str = "", **kw):
    from core_ranks import require
    if not await require(message, bot, 4):
        return
    a = (args or "").strip()
    uid, name, _ = await resolve_target(message, a, bot)
    if not uid:
        return await message.reply(
            "🤔 У кого снять? Укажите <code>@ник</code> или ответьте "
            "на сообщение.")
    row = await db.fetchone("SELECT until FROM vip WHERE user_id=?", (uid,))
    if not row or int(row["until"] or 0) <= int(time.time()):
        return await message.reply(f"У {mention_id(uid, name)} и так нет выпки.")
    await db.execute("DELETE FROM vip WHERE user_id=?", (uid,))
    await message.reply(f"🚫 Выпка снята у {mention_id(uid, name)}")


@router.message(Cmd("кто с выпкой", "список выпок", "выпки", "вип лист",
                    section=S, rank=1, usage="кто с выпкой",
                    desc="Список участников с выпкой"))
async def cmd_vip_list(message: Message, bot: Bot, **kw):
    from core_ranks import require
    if not await require(message, bot, 1):
        return
    now = int(time.time())
    rows = await db.fetchall(
        "SELECT v.user_id, v.until, u.first_name, u.username FROM vip v "
        "LEFT JOIN users u ON u.user_id=v.user_id "
        "WHERE v.until > ? ORDER BY v.until DESC LIMIT 40", (now,))
    if not rows:
        return await message.reply(
            "👑 Сейчас ни у кого нет выпки.\n\n"
            "Выдать: <code>выдать выпку @ник 7 дней</code>")
    out = [f"👑 <b>С выпкой: {len(rows)}</b>\n"]
    for r in rows:
        nm = r["first_name"] or (f"@{r['username']}" if r["username"] else str(r["user_id"]))
        left = int(r["until"]) - now
        term = "навсегда" if int(r["until"]) > 4000000000 else human_period(left)
        out.append(f"👑 {mention_id(r['user_id'], nm)} — ещё {term}")
    await message.reply("\n".join(out), disable_web_page_preview=True)
