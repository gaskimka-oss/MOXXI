import asyncio
import db

async def test():
    await db.init()
    ann_id = await db.create_announcement(-1003934033202, 8412527198, "Тестовый анонс", "Текст тестового анонса")
    print(f"Created announcement ID: {ann_id}")
    assert ann_id > 0, "ann_id must be > 0"
    counts = await db.get_announcement_vote_counts(ann_id)
    print(f"Counts: {counts}")
    print("TEST PASSED!")

if __name__ == "__main__":
    asyncio.run(test())
