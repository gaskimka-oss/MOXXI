"""Интеграция с платёжной системой ЮKassa (YooKassa REST API v3).

Поддерживает:
- Создание счетов на оплату в рублях (СБП, банковские карты РФ, Mir Pay, Т-Банк, Сбер);
- Автоматическую проверку статусов платежей в фоновом режиме;
- Мгновенную выдачу VIP, VIP+, ИИ-подписки и монет;
- Оповещение пользователя и создателя об успешной оплате.
"""
from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import db
from utils import money

log = logging.getLogger("moxxibot.yookassa")

SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "1475484").strip()
SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "live_R-Njww4kRciNS-0nNsViJz7Vn7JaRnLDvnJxtz90mLA").strip()
API_URL = "https://api.yookassa.ru/v3/payments"

# Каталог товаров: ключ -> (название, цена_в_рублях, цена_в_звездах, описание)
PRODUCTS = {
    "vip_30": {
        "title": "⭐️ VIP-статус (30 дней)",
        "price_rub": 39.0,
        "price_stars": 25,
        "desc": "+50% к работе, Крит x3.0 по боссам, +50% к бонусу, 5 +реп в день, 1 щит от варна",
        "type": "vip",
        "level": 1,
        "days": 30
    },
    "vipplus_30": {
        "title": "🌟 VIP+ Diamond (30 дней)",
        "price_rub": 79.0,
        "price_stars": 50,
        "desc": "+150% к работе, МЕГА-крит x3.5, Безлимитный ИИ, VIP-темы, 10 +реп, Кейс каждую неделю",
        "type": "vip",
        "level": 2,
        "days": 30
    },
    "ai_pass_30": {
        "title": "🧠 ИИ-Подписка (30 дней)",
        "price_rub": 29.0,
        "price_stars": 15,
        "desc": "Безлимитный ИИ-Ассистент Мокси, свои квизы (+квиз [тема]), расшифровка ГС и Таро",
        "type": "ai_pass",
        "days": 30
    },
    "coins_50k": {
        "title": "🍬 50 000 монет",
        "price_rub": 5.0,
        "price_stars": 5,
        "desc": "50 000 игровых монет на баланс",
        "type": "coins",
        "amount": 50_000
    },
    "coins_250k": {
        "title": "🎁 250 000 монет",
        "price_rub": 10.0,
        "price_stars": 7,
        "desc": "250 000 игровых монет на баланс",
        "type": "coins",
        "amount": 250_000
    },
    "coins_1m": {
        "title": "🍬 1 000 000 монет (1kk)",
        "price_rub": 15.0,
        "price_stars": 10,
        "desc": "1 000 000 игровых монет на баланс",
        "type": "coins",
        "amount": 1_000_000
    },
    "coins_3m": {
        "title": "🎁 3 000 000 монет (3kk)",
        "price_rub": 35.0,
        "price_stars": 20,
        "desc": "3 000 000 игровых монет на баланс",
        "type": "coins",
        "amount": 3_000_000
    },
    "coins_7m": {
        "title": "💎 7 000 000 монет (7kk)",
        "price_rub": 69.0,
        "price_stars": 35,
        "desc": "7 000 000 игровых монет на баланс",
        "type": "coins",
        "amount": 7_000_000
    },
    "coins_12m": {
        "title": "👑 12 000 000 монет (12kk)",
        "price_rub": 99.0,
        "price_stars": 55,
        "desc": "12 000 000 игровых монет на баланс",
        "type": "coins",
        "amount": 12_000_000
    },
    "coins_20m": {
        "title": "🏆 20 000 000 монет (20kk)",
        "price_rub": 149.0,
        "price_stars": 80,
        "desc": "20 000 000 игровых монет на баланс (максимальный пакет)",
        "type": "coins",
        "amount": 20_000_000
    },
}


def _auth_header() -> str:
    cred = f"{SHOP_ID}:{SECRET_KEY}".encode("utf-8")
    return f"Basic {base64.b64encode(cred).decode('utf-8')}"


def is_configured() -> bool:
    return bool(SHOP_ID and SECRET_KEY and len(SECRET_KEY) > 10)


async def create_rub_payment(user_id: int, item_key: str, bot_username: str = "moxxichat_bot") -> tuple[str | None, str | None]:
    """Создает платёж в ЮKassa и возвращает (confirmation_url, payment_id)."""
    if not is_configured():
        log.warning("ЮKassa не настроена (нет SHOP_ID или SECRET_KEY)")
        return None, None

    prod = PRODUCTS.get(item_key)
    if not prod:
        return None, None

    amount_val = f"{prod['price_rub']:.2f}"
    idem_key = str(uuid.uuid4())
    
    payload = {
        "amount": {
            "value": amount_val,
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{bot_username}"
        },
        "capture": True,
        "description": f"{prod['title']} для ID {user_id}",
        "metadata": {
            "user_id": user_id,
            "item_key": item_key
        }
    }

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": idem_key,
        "Authorization": _auth_header()
    }

    req = urllib.request.Request(API_URL, data=body, headers=headers)

    def _do_request():
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            log.error("Ошибка создания платежа ЮKassa HTTP %s: %s", e.code, err_body)
            return None
        except Exception as e:
            log.error("Сетевая ошибка ЮKassa: %s", e)
            return None

    res = await asyncio.to_thread(_do_request)
    if not res:
        return None, None

    payment_id = res.get("id")
    conf = res.get("confirmation", {})
    pay_url = conf.get("confirmation_url")

    if payment_id and pay_url:
        now = int(time.time())
        await db.execute(
            "INSERT INTO yookassa_payments (id, user_id, item_key, amount_rub, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payment_id, user_id, item_key, prod["price_rub"], "pending", now, now)
        )
        return pay_url, payment_id

    return None, None


async def get_payment_status(payment_id: str) -> str | None:
    """Запрашивает актуальный статус платежа в API ЮKassa."""
    if not is_configured():
        return None

    headers = {
        "Authorization": _auth_header()
    }
    url = f"{API_URL}/{payment_id}"
    req = urllib.request.Request(url, headers=headers)

    def _do_get():
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status")
        except Exception as e:
            log.warning("Ошибка проверки статуса ЮKassa %s: %s", payment_id, e)
            return None

    return await asyncio.to_thread(_do_get)


async def fulfill_payment(bot: Bot, payment_id: str) -> bool:
    """Выдает товар пользователю после подтверждения оплаты."""
    row = await db.fetchone("SELECT * FROM yookassa_payments WHERE id=?", (payment_id,))
    if not row or row["status"] == "succeeded":
        return False

    item_key = row["item_key"]
    user_id = row["user_id"]
    prod = PRODUCTS.get(item_key)
    if not prod:
        return False

    now = int(time.time())
    await db.execute("UPDATE yookassa_payments SET status='succeeded', updated_at=? WHERE id=?", (now, payment_id))

    # Выдача товара в зависимости от типа
    p_type = prod.get("type")

    if p_type == "coins":
        amount = prod["amount"]
        new_bal = await db.add_balance(user_id, amount, "yookassa_coins", payment_id)
        try:
            await bot.send_message(
                user_id,
                f"🎉 ✨ <b>ОПЛАТА УСПЕШНО ЗАВЕРШЕНА!</b> ✨ 🎉\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"📦 <b>Товар:</b> {prod['title']}\n"
                f"💰 <b>Начислено:</b> +{money(amount)}\n"
                f"🍬 <b>Текущий баланс:</b> {money(new_bal)}\n\n"
                f"👑 <i>Спасибо за поддержку проекта! Приятной игры!</i>"
            )
        except Exception:
            pass

    elif p_type == "vip":
        level = prod.get("level", 1)
        days = prod.get("days", 30)
        old_lvl, old_until, old_act = await db.get_vip_info(user_id)
        
        # Защита от даунгрейда: если уже VIP+, не понижаем до VIP, а продлеваем VIP+!
        if old_act and old_lvl >= 2 and level < 2:
            base_ts = old_until if old_until > now else now
            new_until = base_ts + days * 86400
            await db.set_vip(user_id, new_until, 2)
            lvl_name = "🌟 VIP+ Diamond"
            msg_note = f"💎 Так как у вас уже действовал статус <b>🌟 VIP+ Diamond</b>, он был успешно <b>продлён на {days} дней</b> без понижения привилегий!"
        elif level == 2 and old_act and old_lvl == 1:
            # Апгрейд с VIP до VIP+
            new_until = now + days * 86400
            await db.set_vip(user_id, new_until, 2)
            lvl_name = "🌟 VIP+ Diamond"
            msg_note = f"🎉 <b>Поздравляем с апгрейдом до 🌟 VIP+ Diamond на {days} дней!</b> Вам доступны все темы и суперсилы!"
        else:
            base_ts = old_until if (old_act and old_until > now and old_lvl == level) else now
            new_until = base_ts + days * 86400
            await db.set_vip(user_id, new_until, level)
            lvl_name = "🌟 VIP+ Diamond" if level == 2 else "⭐️ VIP"
            msg_note = f"💎 <b>Активирован статус:</b> <b>{lvl_name}</b> на <b>{days} дней</b>!"

        try:
            await bot.send_message(
                user_id,
                f"👑 ✨ <b>ОПЛАТА УСПЕШНО ЗАВЕРШЕНА!</b> ✨ 👑\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"{msg_note}\n\n"
                f"🔥 <b>Ваши новые привилегии:</b>\n"
                f"• Повышенный заработок на <code>работа</code>\n"
                f"• Усиленный крит и защита в рейдах на Боссов\n"
                f"• Бонусы к дуэлям, рыбалке и репутации\n"
                f"• Эксклюзивные темы в <code>вип меню</code>\n\n"
                f"🚀 <i>Статус уже активен во всех ваших беседах!</i>"
            )
        except Exception:
            pass

    elif p_type == "ai_pass":
        days = prod.get("days", 30)
        old_until, old_act = await db.get_ai_pass_info(user_id)
        base_ts = old_until if (old_act and old_until > now) else now
        new_until = base_ts + days * 86400
        await db.set_ai_pass(user_id, new_until)

        try:
            await bot.send_message(
                user_id,
                f"🧠 ✨ <b>ИИ-ПОДПИСКА УСПЕШНО АКТИВИРОВАНА!</b> ✨ 🧠\n"
                f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                f"💎 <b>Срок действия:</b> <b>{days} дней</b>!\n\n"
                f"🔥 <b>Вам доступны все суперсилы ИИ:</b>\n"
                f"• Безлимитное общение с Мокси без задержек (<code>ии [вопрос]</code>)\n"
                f"• Запуск своих викторин в чате: <code>+квиз [любая тема]</code>\n"
                f"• Безлимитная расшифровка голосовых и кружков\n"
                f"• Карты Таро и Гороскопы дня\n\n"
                f"✨ <i>Наслаждайтесь всеми возможностями нейросети!</i>"
            )
        except Exception:
            pass

    # Оповещаем владельцев и поздравляем игрока во всех беседах
    try:
        await broadcast_purchase(
            bot=bot,
            user_id=user_id,
            item_title=prod["title"],
            pay_system="💳 ЮKassa (Рубли / СБП)",
            amount_str=f"{prod['price_rub']:.2f} ₽"
        )
    except Exception as e:
        log.warning("Ошибка broadcast_purchase в ЮKassa: %s", e)

    return True


async def broadcast_purchase(bot: Bot, user_id: int, item_title: str, pay_system: str, amount_str: str) -> None:
    """Оповещает все активные группы о покупке и отправляет персональное уведомление владельцам бота."""
    import config
    from utils import mention_id
    u_row = await db.fetchone("SELECT first_name, username FROM users WHERE user_id=?", (user_id,))
    u_name = u_row["first_name"] if u_row and u_row["first_name"] else "Игрок"
    user_tag = mention_id(user_id, u_name)

    # 1. Личное уведомление всем владельцам бота (Fanat & Simba)
    owner_msg = (
        "💰 👑 <b>[MOXXI SHOP] НОВАЯ ОПЛАТА!</b> 👑 💰\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👤 <b>Покупатель:</b> {user_tag} (ID: <code>{user_id}</code>)\n"
        f"📦 <b>Товар:</b> <b>{item_title}</b>\n"
        f"💳 <b>Платёжная система:</b> <b>{pay_system}</b>\n"
        f"💵 <b>Сумма:</b> <b>{amount_str}</b>\n"
        f"⏰ <b>Время:</b> {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )
    for oid in getattr(config, "BOT_OWNERS", {config.OWNER_ID}):
        try:
            await bot.send_message(oid, owner_msg)
        except Exception:
            pass

    # 2. Праздничное поздравление во все активные беседы с ботом
    group_msg = (
        "🎉 👑 <b>НОВАЯ ПОКУПКА В MOXXI!</b> 👑 🎉\n"
        "✦ ══ • ⊰ 💖 🔮 🎰 🪙 🍷 👑 ⊱ • ══ ✦\n\n"
        f"🌟 Игрок {user_tag} только что приобрёл(а):\n"
        f"💎 <b>{item_title}</b>!\n\n"
        f"💳 <b>Оплата:</b> {pay_system} ({amount_str})\n"
        f"🚀 <i>Поздравляем с приобретением и благодарим за поддержку проекта!</i>\n\n"
        f"🛍 <i>Приобрести VIP, ИИ и монеты:</i> <code>купить вип</code> <i>или кнопка «Магазин» в ЛС!</i>"
    )

    try:
        chat_rows = await db.fetchall(
            "SELECT DISTINCT chat_id FROM chats WHERE chat_id < 0 AND silent = 0 "
            "UNION SELECT DISTINCT chat_id FROM ranks WHERE chat_id < 0 "
            "UNION SELECT DISTINCT chat_id FROM settings WHERE chat_id < 0"
        )
        for r in chat_rows:
            cid = r["chat_id"]
            try:
                await bot.send_message(cid, group_msg)
                await asyncio.sleep(0.05)
            except Exception:
                continue
    except Exception as e:
        log.warning("broadcast_purchase error: %s", e)


async def yookassa_poller(bot: Bot) -> None:
    """Фоновый воркер: проверяет статус незавершенных платежей за последние 2 часа."""
    while True:
        try:
            await asyncio.sleep(20)
            now = int(time.time())
            since = now - 7200  # 2 часа

            pending = await db.fetchall(
                "SELECT id FROM yookassa_payments WHERE status='pending' AND created_at >= ?",
                (since,)
            )
            for r in pending:
                pid = r["id"]
                st = await get_payment_status(pid)
                if st == "succeeded":
                    log.info("Платёж ЮKassa %s подтверждён! Начисляю товар...", pid)
                    await fulfill_payment(bot, pid)
                elif st in ("canceled", "cancelled"):
                    await db.execute("UPDATE yookassa_payments SET status='canceled', updated_at=? WHERE id=?", (now, pid))
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("yookassa_poller error: %s", e)
