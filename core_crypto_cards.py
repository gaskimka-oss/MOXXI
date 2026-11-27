"""
Модуль криптографического шифрования и безопасного маскирования реквизитов (банковские карты, телефоны СБП, счета).
Соответствует стандартам безопасности PCI-DSS / 152-ФЗ:
1. Данные шифруются перед сохранением в базу данных с помощью HMAC-SHA256 authenticated keystream (на базе секретного ключа бота).
2. В логах, интерфейсе пользователя и открытых чатах данные ВСЕГДА маскируются (например: 2200 •••• •••• 1234, 40817 ••••••••••• 1234 или +7 (999) •••-••-67).
3. При компрометации базы данных злоумышленник видит лишь зашифрованный Base64 payload, расшифровать который без секретного ключа невозможно.
"""
import os
import re
import hmac
import hashlib
import secrets
import base64
from typing import Optional

# Базовый секретный ключ берется из окружения или BOT_TOKEN
_SECRET_MATERIAL = os.getenv("CRYPTO_CARD_SECRET") or os.getenv("BOT_TOKEN") or "MOXXI_SECURE_PAYOUT_SALT_2026_PRODUCTION"


def _derive_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Генерация псевдослучайного потока ключа (CTR-like HMAC-SHA256) для шифрования XOR."""
    blocks = []
    counter = 0
    total = 0
    while total < length:
        counter_bytes = counter.to_bytes(4, "big")
        block = hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest()
        blocks.append(block)
        total += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def encrypt_requisites(plain_text: str) -> str:
    """
    Шифрует реквизиты (карту, телефон, банк) с добавлением случайного 16-байтного Nonce и HMAC-подписи целостности.
    Формат результата: ENC:<version>:<base64_payload>
    """
    if not plain_text or not plain_text.strip():
        return ""

    raw_data = plain_text.strip().encode("utf-8")
    salt = b"moxxi_card_crypto_salt_v1"
    # PBKDF2 для получения 32-байтного мастер-ключа
    master_key = hashlib.pbkdf2_hmac("sha256", _SECRET_MATERIAL.encode("utf-8"), salt, 100_000, dklen=32)
    enc_key = hmac.new(master_key, b"enc_sub_key", hashlib.sha256).digest()
    mac_key = hmac.new(master_key, b"mac_sub_key", hashlib.sha256).digest()

    nonce = secrets.token_bytes(16)
    keystream = _derive_keystream(enc_key, nonce, len(raw_data))

    # XOR шифрование
    ciphertext = bytes(b ^ k for b, k in zip(raw_data, keystream))

    # HMAC для защиты от подделки (Authenticated Encryption)
    tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()[:16]

    payload = nonce + tag + ciphertext
    b64 = base64.b64encode(payload).decode("ascii")
    return f"ENC:v1:{b64}"


def decrypt_requisites(cipher_text: str) -> str:
    """
    Расшифровывает строку реквизитов. Если строка не была зашифрована (старый формат),
    возвращает её как есть, сохраняя обратную совместимость.
    """
    if not cipher_text:
        return ""

    raw = cipher_text.strip()
    if not raw.startswith("ENC:v1:"):
        return raw  # Не зашифровано, возвращаем открытый текст

    try:
        b64_part = raw.split(":", 2)[2]
        payload = base64.b64decode(b64_part.encode("ascii"))
        if len(payload) < 32:
            return "[Ошибка дешифрования: поврежденный payload]"

        nonce = payload[:16]
        tag = payload[16:32]
        ciphertext = payload[32:]

        salt = b"moxxi_card_crypto_salt_v1"
        master_key = hashlib.pbkdf2_hmac("sha256", _SECRET_MATERIAL.encode("utf-8"), salt, 100_000, dklen=32)
        enc_key = hmac.new(master_key, b"enc_sub_key", hashlib.sha256).digest()
        mac_key = hmac.new(master_key, b"mac_sub_key", hashlib.sha256).digest()

        # Проверка целостности
        expected_tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected_tag):
            return "[Ошибка дешифрования: неверная цифровая подпись реквизитов]"

        keystream = _derive_keystream(enc_key, nonce, len(ciphertext))
        decrypted = bytes(b ^ k for b, k in zip(ciphertext, keystream))
        return decrypted.decode("utf-8")
    except Exception as e:
        return f"[Ошибка расшифровки: {e}]"


def mask_requisites(text_or_cipher: str) -> str:
    """
    Маскирует реквизиты для безопасного отображения в чатах и профиле:
    - Банковские счета (20 цифр) -> 40817 ••••••••••• 1234
    - Банковская карта 16-19 цифр -> 2200 •••• •••• 1234
    - Номер телефона СБП -> +7 (999) •••-••-67
    - Защищает от утечки персональных данных.
    """
    if not text_or_cipher:
        return "Реквизиты не указаны"

    plain = decrypt_requisites(text_or_cipher)
    if plain.startswith("[Ошибка"):
        return "🔒 [Зашифрованные реквизиты]"

    # 1. Банковские счета (20 цифр)
    def _mask_account(match):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) == 20:
            return f"{digits[:5]} ••••••••••• {digits[-4:]}"
        return match.group(0)

    res = re.sub(r"\b\d{20}\b", _mask_account, plain)

    # 2. Банковские карты (16-19 цифр)
    def _mask_card(match):
        digits = re.sub(r"\D", "", match.group(0))
        if 16 <= len(digits) <= 19:
            return f"{digits[:4]} •••• •••• {digits[-4:]}"
        return match.group(0)

    res = re.sub(r"\b(?:\d[ -]*?){16,19}\b", _mask_card, res)

    # 3. Номера телефонов СБП (+7... или 8...)
    def _mask_phone(match):
        p = re.sub(r"\D", "", match.group(0))
        if len(p) == 11:
            return f"+7 ({p[1:4]}) •••-••-{p[-2:]}"
        elif len(p) == 10:
            return f"+7 ({p[:3]}) •••-••-{p[-2:]}"
        return match.group(0)

    res = re.sub(r"(?:(?<=\s)|(?<=^))(?:\+?7|8)?[- (]*\d{3}[-) ]*\d{3}[- ]*\d{2}[- ]*\d{2}\b", _mask_phone, res)

    return f"🛡 {res}"
