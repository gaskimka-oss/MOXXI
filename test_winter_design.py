import asyncio
import db
import core_themes

async def test_winter_design():
    await db.init()

    # 1. Проверка новогодней темы в дизайне
    assert "new_year_2027" in core_themes.ALL_THEMES
    ny_theme = core_themes.ALL_THEMES["new_year_2027"]
    assert ny_theme["badge"] == "🎄"
    assert "2027" in ny_theme["name"]
    assert "🎄" in ny_theme["banner"]
    print("THEME CHECK: 'new_year_2027' registered in core_themes successfully!")

    # 2. Проверка форматирования хедера и разделителя
    fake_chat = -100999888
    await core_themes.set_chat_theme(fake_chat, "new_year_2027")
    t = await core_themes.get_chat_theme(fake_chat)
    assert t["id"] == "new_year_2027"
    hdr = await core_themes.format_header(fake_chat, "НОВОГОДНИЙ СОВЕТ")
    assert "🎄" in hdr
    div = await core_themes.format_divider(fake_chat)
    assert "❄️" in div
    print("CHAT DESIGN CHECK: Theme 'new_year_2027' applies to chat correctly!")

    # 3. Проверка таблицы писем Санте
    import h_winter_event as winter
    await winter._init_santa_letters_table()
    await db.execute(
        "INSERT INTO santa_letters (user_id, user_name, chat_id, wish, created_at) "
        "VALUES (12345, 'Гасим', -1001, 'Хочу счастья и топ-бота', 1700000000)"
    )
    row = await db.fetchone("SELECT * FROM santa_letters WHERE user_id = 12345")
    assert row is not None
    assert row["wish"] == "Хочу счастья и топ-бота"
    print("SANTA LETTERS CHECK: Letter saved and fetched correctly!")

    print("\nALL NEW YEAR DESIGN & EVENT CHECKS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_winter_design())
