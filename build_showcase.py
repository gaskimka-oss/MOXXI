import base64
import os

ARTIFACT_DIR = r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9"
DESKTOP_DIR = r"c:\Users\eiema\OneDrive\Desktop\бот2.0\avatars"

featured_moxxi_avatars = [
    {
        "title": "🤖 Главный Бот: MOXXI",
        "file": "moxxistyle_1_bot.png",
        "badge": "ГЛАВНЫЙ БОТ",
        "badge_color": "border-cyan-500/40 text-cyan-300 bg-cyan-500/10",
        "desc": "Официальная аватарка главного бота. Чистый неоновый арт Moxxi с плашкой «ГЛАВНЫЙ БОТ» в фирменном электрическом циане (Cyber Cyan).",
        "for_what": "Для профиля @moxxichat_bot в @BotFather"
    },
    {
        "title": "💡 Идеи и Предложения",
        "file": "moxxistyle_2_ideas.png",
        "badge": "ИДЕИ И ПРЕДЛОЖЕНИЯ",
        "badge_color": "border-pink-500/40 text-pink-300 bg-pink-500/10",
        "desc": "Аватарка для группы предложений и голосований. Неоновый текст в оттенке сочной мадженты / фиолетового (Neon Magenta).",
        "for_what": "Для группы предложений и голосования (+чат идей)"
    },
    {
        "title": "💬 Чат Сообщества",
        "file": "moxxistyle_3_chat.png",
        "badge": "ЧАТ СООБЩЕСТВА",
        "badge_color": "border-teal-500/40 text-teal-300 bg-teal-500/10",
        "desc": "Аватарка для официальной беседы общения игроков. Надпись в бирюзово-мятном неоне (Electric Mint) с киберпанк свечением.",
        "for_what": "Для официальной беседы общения игроков (+чат общения)"
    },
    {
        "title": "⭐ Отзывы и Рейтинг",
        "file": "moxxistyle_4_reviews.png",
        "badge": "ОТЗЫВЫ И РЕЙТИНГ",
        "badge_color": "border-yellow-500/40 text-yellow-300 bg-yellow-500/10",
        "desc": "Аватарка для группы/канала отзывов. Богатый неоновый золотой цвет (Cyber Gold / Amber), идеально сочетающийся с золотыми элементами наряда.",
        "for_what": "Для официального канала/группы с отзывами (+чат отзывов)"
    },
    {
        "title": "🛡️ Техническая Поддержка",
        "file": "moxxistyle_5_support.png",
        "badge": "ТЕХ. ПОДДЕРЖКА",
        "badge_color": "border-emerald-500/40 text-emerald-300 bg-emerald-500/10",
        "desc": "Аватарка для группы тикетов и связи с саппортом. Изумрудно-неоновый оттенок безопасности (Emerald Neon).",
        "for_what": "Для закрытой группы модераторов / техподдержки (+чат поддержки)"
    }
]

def to_b64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = f.read()
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"

cards_html = []
for item in featured_moxxi_avatars:
    p = os.path.join(ARTIFACT_DIR, item["file"])
    b64 = to_b64(p)

    card = f"""
    <div class="bg-[#120a26] rounded-3xl p-6 border border-pink-500/30 shadow-2xl flex flex-col md:flex-row gap-6 items-center hover:border-cyan-400/50 transition-all">
        <div class="relative group flex-shrink-0">
            <img src="{b64}" alt="{item['title']}" class="w-56 h-56 rounded-2xl object-cover shadow-2xl border-2 border-cyan-400/50 group-hover:scale-105 transition-all">
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-all flex items-end p-3">
                <span class="text-xs text-cyan-200 font-mono">1024x1024 HD</span>
            </div>
        </div>
        <div class="flex-1 space-y-3 text-left">
            <div class="flex flex-wrap items-center gap-3">
                <span class="px-3 py-1 rounded-full text-xs font-bold border {item['badge_color']}">{item['badge']}</span>
                <h3 class="text-2xl font-black text-white">{item['title']}</h3>
            </div>
            <p class="text-sm text-gray-300 leading-relaxed">{item['desc']}</p>
            <div class="p-3 rounded-xl bg-black/40 border border-white/5 space-y-1">
                <div class="text-xs text-cyan-300 font-semibold">🎯 Назначение: {item['for_what']}</div>
                <div class="text-xs text-gray-400 font-mono">📁 Файл: <span class="text-pink-300">avatars/{item['file']}</span></div>
            </div>
        </div>
    </div>
    """
    cards_html.append(card)

html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Moxxi Bot Style Avatars</title>
    <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-[#0b0716] text-white p-6 min-h-screen">
    <div class="max-w-4xl mx-auto space-y-8">
        <div class="text-center space-y-3">
            <div class="inline-block px-4 py-1.5 rounded-full bg-gradient-to-r from-pink-500/20 to-cyan-500/20 border border-cyan-400/40 text-cyan-300 font-semibold text-xs tracking-wider">
                🌟 ОФИЦИАЛЬНЫЙ НАБОР В СТИЛЕ MOXXI (БЕЗ СЛЕПЯЩЕГО БЕЛОГО)
            </div>
            <h1 class="text-4xl font-black tracking-tight bg-gradient-to-r from-pink-400 via-purple-300 to-cyan-400 bg-clip-text text-transparent">
                5 Аватарок в Стиле Вашего Арта Moxxi
            </h1>
            <p class="text-sm text-gray-400 max-w-xl mx-auto">
                Все надписи переведены в гармоничные неоновые цвета (циановый, маджента, мятный, золотой, изумрудный). Исходное качество 1024x1024 сохранено в папке <code class="text-pink-400 bg-black/50 px-2 py-0.5 rounded">avatars/</code>!
            </p>
        </div>

        <div class="space-y-6">
            {"".join(cards_html)}
        </div>
    </div>
</body>
</html>
"""

out_path = os.path.join(ARTIFACT_DIR, "avatars_showcase.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Showcase built at {out_path}")
