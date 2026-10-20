import os
import re

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    orig = content
    # Clean ZRGG_Oblivion_bot or ZRGOblivion mentions
    content = content.replace("@ZRGG_Oblivion_bot", "@moxxichat_bot")
    content = content.replace("ZRGG_Oblivion_bot", "moxxichat_bot")
    content = content.replace("ZRGOblivion", "MOXXI")
    content = content.replace("Oblivion", "MOXXI")

    # Clean specific iris commands
    content = re.sub(r'Cmd\("инфа",\s*"ирис инфа",', 'Cmd("инфа",', content)
    content = re.sub(r'Cmd\("ирис",\s*"ирис профиль",', 'Cmd("профиль бота", "бот профиль",', content)

    if content != orig:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")

for root, dirs, files in os.walk('.'):
    if '.venv' in root or 'venv' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            clean_file(os.path.join(root, file))

print("Cleanup completed.")
