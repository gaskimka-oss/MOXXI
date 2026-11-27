import asyncio
import time
import db
from core_crypto_cards import encrypt_requisites, decrypt_requisites, mask_requisites

async def test_full_crypto_flow():
    await db.init()
    test_user_id = 999111222
    card_raw = "2200 4567 8901 3344 Сбербанк МИР"

    # 1. Привязка реквизитов
    await db.set_creator_requisites(test_user_id, card_raw)
    w = await db.get_or_create_creator_wallet(test_user_id)
    saved_req = w.get("card_requisites", "")

    print(f"RAW INPUT:        {card_raw}")
    print(f"STORED IN DB:     {saved_req[:35]}...")
    assert saved_req.startswith("ENC:v1:"), f"Must be encrypted in DB! Got: {saved_req}"
    assert "4567 8901" not in saved_req, "DB contains raw card number!"

    # 2. Проверка расшифровки
    decrypted = decrypt_requisites(saved_req)
    assert decrypted == card_raw, f"Decryption mismatch: {decrypted} != {card_raw}"
    print(f"DECRYPTED FOR PAYOUT: {decrypted}")

    # 3. Проверка маскирования
    masked = mask_requisites(saved_req)
    assert "2200 •••• •••• 3344" in masked, f"Mask failure: {masked}"
    print(f"MASKED FOR CHAT:      {masked}")

    # 4. Проверка заявки на вывод
    await db.credit_creator_earnings(test_user_id, 1000.0)
    p_id = await db.create_payout_request(
        user_id=test_user_id,
        chat_id=-1001234567,
        amount_rub=500.0,
        amount_stars=0,
        method="card",
        requisites=saved_req
    )
    p = await db.get_payout_request(p_id)
    assert p is not None
    assert p["requisites"].startswith("ENC:v1:")
    p_decrypted = decrypt_requisites(p["requisites"])
    assert p_decrypted == card_raw

    res = await db.complete_payout_request(p_id)
    assert res is not None

    print("\nSUCCESS: All database card encryption and masking checks passed 100%!")

if __name__ == "__main__":
    asyncio.run(test_full_crypto_flow())
