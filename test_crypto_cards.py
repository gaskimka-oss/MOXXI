import sys
from core_crypto_cards import encrypt_requisites, decrypt_requisites, mask_requisites

def test_crypto():
    samples = [
        ("2200 1234 5678 9999 Тинькофф МИР", "9999"),
        ("+79991234567 Сбербанк СБП", "67"),
        ("40817810000000001234 Альфа-Банк", "1234"),
        ("89161234567 Т-Банк", "67"),
    ]

    for s, expected_ending in samples:
        enc = encrypt_requisites(s)
        assert enc.startswith("ENC:v1:"), f"Bad enc: {enc}"
        dec = decrypt_requisites(enc)
        assert dec == s, f"Dec mismatch: {dec} != {s}"
        masked = mask_requisites(enc)
        assert expected_ending in masked, f"Bad mask: {masked} doesn't have {expected_ending}"
        assert "1234 5678" not in masked, f"Leaked card data: {masked}"
        print(f"ORIGINAL:  {s}")
        print(f"ENCRYPTED: {enc[:30]}...")
        print(f"MASKED:    {masked}")
        print("-" * 50)

    print("ALL CRYPTO TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_crypto()
