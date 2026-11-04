# -*- coding: utf-8 -*-
"""
MOXXI 3.0 REVOLUTION - Master Video Showcase Generator
Generates full 1080p (1920x1080) / 720p cinematic presentation video with Irina TTS.
"""
import os
import sys
import time
import wave
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
FPS = 24

FONT_DIR = "C:/Windows/Fonts/"
FONTS = {
    "title": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 46),
    "sub": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 26),
    "body": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 22),
    "badge": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 18),
    "footer": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 16),
}

SCENES = [
    {
        "id": "scene1_intro",
        "badge": "🚀 ГЛОБАЛЬНЫЙ РЕЛИЗ 3.0",
        "title": "MOXXI 3.0 REVOLUTION",
        "sub": "Революция Telegram-ботов • 650+ возможностей",
        "bullets": [
            "⚡️ Моментальный отклик 0.01с и нулевой пинг",
            "🛡 Полное исправление конфликтов команд и поиска",
            "🤖 Автоматический AI-перевод голосовых и кружков",
            "💎 Уникальная экономика, биржа акций и синдикаты"
        ],
        "bg_color": (15, 10, 30),
        "accent": (168, 85, 247), # purple
        "text": "Встречайте масштабное глобальное обновление Мокси три точка ноль! Мы полностью переработали ядро бота, устранили все баги и конфликты команд и добавили уникальные возможности для игроков и администраторов!"
    },
    {
        "id": "scene2_webapp",
        "badge": "📱 WEB APP БЕЗ VPN",
        "title": "НЕОНОВОЕ КАЗИНО И БИЗНЕСЫ",
        "sub": "Слоты 777 • Мины х550 • 3D Кости • 15 Предприятий",
        "bullets": [
            "🚀 100% автономная работа без белых экранов и VPN",
            "🎰 Множители ставок x1, x2, x3, x5, x9, x10",
            "💣 Выбор сложности в Минах (2, 3, 5, 8 бомб)",
            "🎁 Ежедневный бонус со стриком и честным 4-часовым КД"
        ],
        "bg_color": (8, 20, 25),
        "accent": (6, 182, 212), # cyan
        "text": "Главная новинка — автономный Веб Апп три точка ноль, который открывается мгновенно без ВПН! Новые множители ставок от одного до десяти икс в Слотах, выбор бомб в игре Мины с кушем до пятисот пятидесяти икс и интерактивные три дэ кости!"
    },
    {
        "id": "scene3_syndicates",
        "badge": "🏙 БИТВА ЗА ГОРОД",
        "title": "СИНДИКАТЫ И ВОЙНЫ ЗА РАЙОНЫ",
        "sub": "5 районов города • Казна клана • Пассивный доход",
        "bullets": [
            "⚔️ Основание синдиката и набор бойцов",
            "🌆 Штурм и контроль районов: Центр, Финансы, Доки, Бункер, Казино",
            "💰 Ежедневная дань прямо в казну синдиката",
            "🏆 Сезонный рейтинг сильнейших группировок"
        ],
        "bg_color": (25, 12, 10),
        "accent": (239, 68, 68), # red/orange
        "text": "Для игроков запущена система Синдикатов! Создавайте свои альянсы, прокачивайте боевой рейтинг и захватывайте городские районы. Контроль Центрального Неона и Квартала Казино приносит ежедневную дань прямо в казну!"
    },
    {
        "id": "scene4_tg_games",
        "badge": "🎲 ИГРЫ TELEGRAM DICE",
        "title": "ЭМОДЗИ-КАЗИНО С ФИЗИКОЙ",
        "sub": "🎯 Дартс • 🏀 Баскетбол • 🎳 Боулинг • ⚽️ Футбол",
        "bullets": [
            "🎯 Дартс: бросок в яблочко с коэффициентом х3.5!",
            "🏀 Баскетбол: попадание в кольцо с кушем х2.5!",
            "🎳 Боулинг: страйк всеми кеглями с выигрышем х4.0!",
            "⚽️ Футбол: пенальти в девятку с коэффициентом х2.2!"
        ],
        "bg_color": (10, 26, 16),
        "accent": (16, 185, 129), # green
        "text": "Испытайте удачу в настоящих Телеграм играх с живой анимацией кубиков! Дартс в яблочко с коэффициентом три с половиной, броски в кольцо, страйки в боулинге и пенальти в футболе!"
    },
    {
        "id": "scene5_exchange_ai",
        "badge": "💎 ОБМЕННИК & ИИ STT",
        "title": "VIP ЗА МОНЕТЫ И АВТО-ГОЛОС",
        "sub": "Покупка VIP за игровую валюту • Распознавание ГС и кружков",
        "bullets": [
            "⭐ 3 дня VIP (50кк), 7 дней VIP (150кк), 30 дней VIP+ Diamond (500кк)",
            "🎤 Авто-распознавание ГС и видео-кружков прямо в группах",
            "📈 Фондовая биржа 5 корпораций, дивиденды и портфель",
            "📦 Секретные кейсы 3.0 с редким лутом и миллионными кушами"
        ],
        "bg_color": (26, 20, 8),
        "accent": (234, 179, 8), # gold
        "text": "Накопленные игровые миллионы теперь можно обменять на VIP и VIP плюс Даймонд статусы прямо в обменнике! А встроенная нейросеть автоматически переводит любые голосовые сообщения и кружочки в читаемый текст без лишних команд!"
    },
    {
        "id": "scene6_admin_shield",
        "badge": "🛡 БЕЗОПАСНОСТЬ 3.0",
        "title": "ПРОФЕССИОНАЛЬНЫЙ АДМИН-ЩИТ",
        "sub": "Карантин новичков • Чистка сервиса • Умная модерация",
        "bullets": [
            "🛡 Карантин новичков: защита группы от спам-атак и скам-ботов",
            "🧹 Команда «чистить сервис»: удаление входов, выходов и закрепов",
            "💡 Умные подсказки ДК: кликабельная помощь при отказе прав",
            "🎯 Идеально точный поиск «найти бан» без банковской путаницы"
        ],
        "bg_color": (18, 12, 35),
        "accent": (147, 51, 234), # violet
        "text": "Для администраторов доступны режим карантина новичков, скрытый тихий бан, экспресс чистка сервисных сообщений и подробные подсказки по настройке прав команд через Де Ка. Присоединяйтесь к Мокси три точка ноль!"
    }
]

def generate_voice(text, wav_path):
    txt_temp = wav_path + ".txt"
    with open(txt_temp, "w", encoding="utf-8") as f:
        f.write(text)
    cmd = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", ".\\tts_helper.ps1",
        "-TextFile", txt_temp,
        "-OutFile", wav_path
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(txt_temp):
        os.remove(txt_temp)

def get_wav_duration(wav_path):
    with wave.open(wav_path, "rb") as w:
        return w.getnframes() / float(w.getframerate())

def render_scene(sc, idx, total):
    wav_path = f"temp_sc_{sc['id']}.wav"
    mp4_path = f"temp_sc_{sc['id']}.mp4"
    print(f"[{idx}/{total}] Synthesizing TTS for {sc['id']}...")
    generate_voice(sc["text"], wav_path)
    dur = get_wav_duration(wav_path) + 0.8
    total_frames = int(dur * FPS)

    print(f"[{idx}/{total}] Rendering {total_frames} frames ({dur:.1f}s) for {sc['id']}...")

    # Start ffmpeg process
    ffmpeg_cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}",
        "-r", str(FPS),
        "-i", "-",
        "-i", wav_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        mp4_path
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    base_bg = sc["bg_color"]
    accent = sc["accent"]

    for f in range(total_frames):
        # Progress 0.0 -> 1.0
        p = f / float(total_frames)

        # Create base canvas with smooth gradient
        img = Image.new("RGB", (W, H), base_bg)
        draw = ImageDraw.Draw(img)

        # Ambient background glow
        glow_alpha = int(40 + 20 * np.sin(p * np.pi * 2))
        draw.ellipse((-100, -100, 600, 600), fill=(accent[0]//5, accent[1]//5, accent[2]//5))
        draw.ellipse((W - 500, H - 400, W + 100, H + 100), fill=(accent[0]//6, accent[1]//6, accent[2]//6))

        # Top Badge
        badge_x, badge_y = 90, 65
        b_w, b_h = 240, 36
        draw.rounded_rectangle((badge_x, badge_y, badge_x + b_w, badge_y + b_h), radius=10, fill=(30, 30, 45), outline=accent, width=2)
        draw.text((badge_x + 16, badge_y + 7), sc["badge"], fill=accent, font=FONTS["badge"])

        # Title with neon underline
        title_y = 125
        draw.text((90, title_y), sc["title"], fill=(255, 255, 255), font=FONTS["title"])
        
        # Subtitle
        sub_y = 188
        draw.text((92, sub_y), sc["sub"], fill=(203, 213, 225), font=FONTS["sub"])

        # Animated Glowing Line
        line_w = int((W - 180) * min(1.0, p * 2.5))
        draw.line((90, 230, 90 + line_w, 230), fill=accent, width=3)

        # Card container for bullets
        card_x, card_y = 90, 260
        card_w, card_h = 1100, 340
        draw.rounded_rectangle((card_x, card_y, card_x + card_w, card_y + card_h), radius=18, fill=(18, 22, 34), outline=(45, 55, 75), width=2)

        # Bullets with animated fade-in
        bullet_start_y = 295
        for b_idx, b_text in enumerate(sc["bullets"]):
            delay = 0.15 * b_idx
            if p >= delay:
                by = bullet_start_y + (b_idx * 60)
                # Bullet icon
                draw.rounded_rectangle((card_x + 30, by + 2, card_x + 48, by + 20), radius=5, fill=accent)
                # Bullet text
                draw.text((card_x + 65, by), b_text, fill=(241, 245, 249), font=FONTS["body"])

        # Bottom Progress Bar
        bar_w = int(W * p)
        draw.rectangle((0, H - 8, bar_w, H), fill=accent)

        # Footer
        draw.text((90, H - 40), f"MOXXI 3.0 REVOLUTION • @moxxichat_bot • Сцена {idx}/{total}", fill=(100, 116, 139), font=FONTS["footer"])

        # Pipe frame bytes
        raw_bytes = img.tobytes()
        proc.stdin.write(raw_bytes)

    proc.stdin.close()
    proc.wait()
    if os.path.exists(wav_path):
        os.remove(wav_path)
    return mp4_path

def main():
    print("=== STARTING FULL MOXXI 3.0 VIDEO SHOWCASE GENERATION ===")
    parts = []
    total = len(SCENES)
    for i, sc in enumerate(SCENES, 1):
        p = render_scene(sc, i, total)
        parts.append(p)

    concat_file = "video_concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p}'\n")

    final_output = "MOXXI_3.0_GLOBAL_UPDATE.mp4"
    print(f"\nConcatenating all {total} scenes into master file: {final_output}...")
    cmd_concat = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        final_output
    ]
    subprocess.run(cmd_concat, check=True)

    # Cleanup temp scene mp4s
    for p in parts:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    if os.path.exists(concat_file):
        try:
            os.remove(concat_file)
        except Exception:
            pass

    size_mb = os.path.getsize(final_output) / (1024 * 1024)
    print(f"🎉 SUCCESS! Final video generated: {final_output} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
