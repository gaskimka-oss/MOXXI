import os
import re

REPLACEMENTS = [
    # Prefix words
    (r'PREFIX_WORDS = \("ириска", "ирис"\)', 'PREFIX_WORDS = ("мокси", "бот")'),
    (r'PREFIX_WORDS = \(\'ириска\', \'ирис\'\)', 'PREFIX_WORDS = ("мокси", "бот")'),
    (r'low\.startswith\("ирис"\) or low\.startswith\("ириска"\)', 'low.startswith("мокси") or low.startswith("бот")'),
    (r'low\.startswith\(\("http", "ирис"\)\)', 'low.startswith(("http", "мокси", "бот"))'),
    
    # Text replacements (case insensitive or exact)
    (r'ирис-биржа', 'биржа монет'),
    (r'Ирис-биржа', 'Биржа монет'),
    (r'ирис-биржах', 'биржах монет'),
    (r'ирис-бирже', 'бирже монет'),
    (r'ирис инфо', 'бот инфо'),
    (r'Ирис инфо', 'Бот инфо'),
    (r'ириски', 'монеты'),
    (r'Ириски', 'Монеты'),
    (r'ирисок', 'монет'),
    (r'Ирисок', 'Монет'),
    (r'ириска', 'монета'),
    (r'Ириска', 'Монета'),
    (r'ириску', 'монету'),
    (r'Ириску', 'Монету'),
    (r'ириской', 'монетой'),
    (r'Ириской', 'Монетой'),
    (r'купить ириски', 'купить монеты'),
    (r'Купить ириски', 'Купить монеты'),
    (r'«я люблю Ирис»', '«я люблю бота»'),
    (r'«Ириска»', '«Котик»'),
    (r'ураган ирисок', 'ураган монет'),
    (r'на ириски', 'на монеты'),
    (r'за ириски', 'за монеты'),
    (r'горсть ирисок', 'горсть монет'),
    (r'мешок ирисок', 'мешок монет'),
    (r'коробка ирисок', 'коробка монет'),
    (r'сундук ирисок', 'сундук монет'),
    (r'Горсть ирисок', 'Горсть монет'),
    (r'Мешок ирисок', 'Мешок монет'),
    (r'Коробка ирисок', 'Коробка монет'),
    (r'Сундук ирисок', 'Сундук монет'),
    (r'по ирискам', 'по монетам'),
    (r'топ по ирискам', 'топ по монетам'),
    (r'топ ирисок', 'топ монет'),
    (r'«Ирис»', '«Менеджер»'),
    (r'Ирис', 'Бот'),
    (r'ирисbot', 'moxxibot'),
    (r'irisbot', 'moxxibot'),
    (r'ZRGOblivion', 'MOXXI'),
]

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    new_content = content
    for pattern, repl in REPLACEMENTS:
        new_content = re.sub(pattern, repl, new_content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Cleaned: {filepath}")

for root, _, files in os.walk('.'):
    if 'venv' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py') or file.endswith('.md') or file.endswith('.txt'):
            clean_file(os.path.join(root, file))

print("All replacements finished!")
