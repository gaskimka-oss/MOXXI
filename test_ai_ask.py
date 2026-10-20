import asyncio
import config
import core_ai as ai

async def test():
    print("ai.available():", ai.available())
    print("ai.KEYS count:", len(ai.KEYS))
    res = await ai.ask_text("Сколько тебе лет?")
    print("ai.ask_text result:", res)

asyncio.run(test())
