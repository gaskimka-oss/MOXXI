import asyncio
from core_registry import Cmd

for c in ['бан', 'кик', 'мут', 'бот', 'кто админ']:
    f = Cmd(c)
    m = type('M', (), {'text': c, 'caption': None, 'chat': type('C', (), {'type': 'supergroup'})(), 'reply_to_message': None})()
    res = asyncio.run(f(m))
    print(c, '->', bool(res))
