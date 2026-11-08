# -*- coding: utf-8 -*-
"""
MOXXI 3.0 REVOLUTION - Master Authentic Telegram Desktop Screencast Generator
Presents:
1. Introduction to MOXXI ("Встречайте бота MOXXI!...")
2. Interactive Profile & Ranks
3. Smart DK Permissions & Helpful Guidance
4. Casino 3.0: European Roulette x36, Dice, Slots
5. Syndicates & City District Clan Wars
6. Admin Shield: Quarantine, Service Clean, Mod Log
7. AI Speech-to-Text: Circles & Voice Notes into text
8. Outro & Invitation

Narrator: Microsoft Neural AI (ru-RU-SvetlanaNeural)
Engine: Pillow RGB24 + FFmpeg Direct Pipe
"""
import os
import sys
import wave
import asyncio
import subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import edge_tts

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
FPS = 15

FONT_DIR = "C:/Windows/Fonts/"
FONTS = {
    "regular": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 17),
    "bold": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 18),
    "header": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 20),
    "small": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 13),
    "small_bold": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 13),
    "input": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 18),
    "title": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 23),
    "mono": ImageFont.truetype(FONT_DIR + "consola.ttf", 15),
}

async def generate_voice_edge(text: str, out_wav: str):
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 10000:
        return
    temp_mp3 = out_wav + ".mp3"
    comm = edge_tts.Communicate(text, "ru-RU-SvetlanaNeural", rate="+6%")
    await comm.save(temp_mp3)

    cmd = [
        FFMPEG, "-y", "-i", temp_mp3,
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
        out_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(temp_mp3):
        os.remove(temp_mp3)

def get_wav_duration(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as w:
        return w.getnframes() / float(w.getframerate())

SCENES = [
    {
        "id": "scene1_intro",
        "voice": (
            "Встречайте бота MOXXI! Это лучший и самый мощный бот для ваших Telegram-бесед и каналов. "
            "Полный контроль над чатом, система рангов, кланы, умная защита и море развлечений прямо в Telegram!"
        ),
        "card_title": "ВСТРЕЧАЙТЕ БОТА MOXXI",
        "card_bullets": [
            ("⚡️", "Умный бот для бесед и каналов"),
            ("👑", "Иерархия рангов от 0 до 8"),
            ("🛡", "Железная защита от спама и рейдов"),
            ("🎮", "Казино, синдикаты, бизнес и Web App")
        ],
        "typing_cmd": "старт",
        "messages": [
            {
                "sender": "Саша",
                "text": "старт",
                "time": "12:00"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "Добро пожаловать в MOXXI 3.0 REVOLUTION!\n\n"
                    "Ваш профиль:\n"
                    "• Имя: Саша (@sasha_tg)\n"
                    "• Ранг в беседе: Участник (Ранг 0)\n"
                    "• Баланс: 250,000 монет\n"
                    "• VIP-статус: Platinum (активен еще 28 дн.)\n\n"
                    "Выберите нужный раздел в меню ниже:"
                ),
                "buttons": ["🎮 Игры и Казино", "💼 Предприятия", "🛡 Админ-панель"],
                "time": "12:00"
            }
        ]
    },
    {
        "id": "scene2_dk_access",
        "voice": (
            "Забудьте о сложных настройках прав! В MOXXI система ДК сама подскажет, как открыть команду. "
            "Если у участника не хватает ранга, бот сразу выведет готовую команду для включения в один клик!"
        ),
        "card_title": "СИСТЕМА ДОСТУПА КОМАНД (ДК)",
        "card_bullets": [
            ("🔒", "Умное управление правами на любую команду"),
            ("💡", "Автоматические подсказки при нехватке прав"),
            ("⚡️", "Включение для всех в одну команду: дк [команда] 0"),
            ("👥", "Личные права: +пдк и -лдк для участников")
        ],
        "typing_cmd": "снять вклад 10000000",
        "messages": [
            {
                "sender": "Саша",
                "text": "снять вклад 10000000",
                "time": "12:01"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "⛔️ Недостаточно прав для команды «снять вклад»!\n\n"
                    "🔒 Требуемый ранг: Технический администратор (Ранг 6)\n"
                    "👤 Ваш текущий ранг: Участник (Ранг 0)\n\n"
                    "💡 Как настроить доступ к этой команде:\n"
                    "• Разрешить команду всем: дк снять вклад 0\n"
                    "• Изменить ранг доступа: дк снять вклад 2\n"
                    "• Выдать личный доступ: +пдк @юзер снять вклад"
                ),
                "buttons": ["💡 Разрешить всем (дк 0)", "ℹ️ Список рангов"],
                "time": "12:01"
            }
        ]
    },
    {
        "id": "scene3_casino_roulette",
        "voice": (
            "Игрокам точно не придётся скучать! Встречайте Неоновое Казино 3.0: классическая европейская рулетка с "
            "множителями до тридцати шести, интерактивный дартс, слоты 777 и блэкджек с реальными кнопками."
        ),
        "card_title": "НЕОНОВОЕ КАЗИНО 3.0",
        "card_bullets": [
            ("🎰", "Европейская Рулетка: выигрыш до x36"),
            ("🎯", "Дартс, Баскетбол, Футбол и Боулинг"),
            ("🃏", "Блэкджек 21 очко с живыми кнопками"),
            ("📱", "Moxxi Web App: Слоты 777 и Мины x550")
        ],
        "typing_cmd": "рулетка 50000 красное",
        "messages": [
            {
                "sender": "Саша",
                "text": "рулетка 50000 красное",
                "time": "12:02"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎰 🎯 ПОБЕДА В РУЛЕТКЕ!\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "Выпало: 14 (красное)\n"
                    "Множитель: x2.0\n"
                    "💰 Выигрыш: +100,000 монет (+50,000 чистыми)!\n"
                    "Баланс: 300,000 монет."
                ),
                "buttons": ["🎡 Крутить еще раз", "🎯 Дартс", "🎰 Слоты"],
                "time": "12:02"
            }
        ]
    },
    {
        "id": "scene4_syndicates",
        "voice": (
            "Синдикаты и Войны за Районы — новая масштабная механика! "
            "Создавайте группировку, штурмуйте пять районов мегаполиса и собирайте ежедневную дань прямо в казну клана."
        ),
        "card_title": "СИНДИКАТЫ И ВОЙНЫ ЗА РАЙОНЫ",
        "card_bullets": [
            ("🏙", "5 районов города: Центр, Казино, Доки, Банк, Бункер"),
            ("⚔️", "Штурм и защита территорий каждый день"),
            ("💰", "Ежедневная дань миллионами в казну"),
            ("🏆", "Топ сильнейших синдикатов города")
        ],
        "typing_cmd": "синдикаты",
        "messages": [
            {
                "sender": "Саша",
                "text": "синдикаты",
                "time": "12:03"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🏙 ⚔️ СИНДИКАТЫ И ВОЙНЫ ЗА РАЙОНЫ\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "1. 🏛 Деловой Центр ➔ Захвачен: [LEGEND] (Дань: 2.5M)\n"
                    "2. 🎰 Район Казино ➔ Захвачен: [PHOENIX] (Дань: 5.0M)\n"
                    "3. ⚓️ Морские Доки ➔ Свободен для штурма!\n"
                    "4. 🏦 Финансовый Квартал ➔ Захвачен: [BEAR]\n"
                    "5. 🛡 Подземный Бункер ➔ Свободен для штурма!\n\n"
                    "Команда штурма: захват района [1-5]"
                ),
                "buttons": ["⚔️ Захватить район 3", "🛡 Казна синдиката"],
                "time": "12:03"
            }
        ]
    },
    {
        "id": "scene5_admin_shield",
        "voice": (
            "Для администраторов подготовлен бронебойный арсенал: антирейд карантин новичков, мгновенная очистка сервисных сообщений, "
            "тихий бан и подробный аудит действий модерации."
        ),
        "card_title": "АДМИНИСТРАТИВНЫЙ ЩИТ 3.0",
        "card_bullets": [
            ("🛡", "Карантин новичков: авто-блокировка ссылок и спама"),
            ("🧹", "Очистка сервисных сообщений (входы, выходы, закрепы)"),
            ("🔒", "Тихий бан без лишнего шума в чате"),
            ("📋", "Полный лог модерации и действий стаффа")
        ],
        "typing_cmd": "карантин 15",
        "messages": [
            {
                "sender": "Саша",
                "text": "карантин 15",
                "time": "12:04"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🛡 ✅ КАРАНТИН НОВИЧКОВ ВКЛЮЧЕН НА 15 МИНУТ!\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "Все новые участники в течение первых 15 минут защищены от спама: "
                    "запрещена отправка ссылок и пересылка медиа.\n"
                    "Ваша беседа под надежной защитой Moxxi!"
                ),
                "buttons": ["🧹 Чистить сервис", "📋 Лог модерации"],
                "time": "12:04"
            }
        ]
    },
    {
        "id": "scene6_stt_ai",
        "voice": (
            "А умный искусственный интеллект MOXXI мгновенно переводит любые голосовые сообщения и видео-кружочки в текст "
            "прямо на лету, без необходимости вводить команды!"
        ),
        "card_title": "ИИ РАСШИФРОВКА КРУЖОЧКОВ И ГС",
        "card_bullets": [
            ("📹", "Мгновенная расшифровка видео-кружочков"),
            ("🎙", "Авто-перевод голосовых сообщений в текст"),
            ("🤖", "Сверхбыстрый мультимодальный ИИ"),
            ("⚡️", "Работает автоматически для всех участников")
        ],
        "typing_cmd": "привет, расскажи коротко о себе!",
        "messages": [
            {
                "sender": "Саша",
                "text": "📹 [Видео-кружочек: 0:04 сек]",
                "time": "12:05"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "📹 Кружочек:\n"
                    "«Ребята, всем привет! Во сколько сегодня собираемся в голосовом чате на турнир?»\n\n"
                    "🤖 MOXXI AI: Автоматическая транскрипция речи выполнена успешно!"
                ),
                "buttons": ["🎙 Настройки распознавания"],
                "time": "12:05"
            }
        ]
    },
    {
        "id": "scene7_outro",
        "voice": (
            "MOXXI 3.0 — это будущее Telegram-ботов уже сегодня. "
            "Сделайте вашу группу самой активной и безопасной. Добавляйте бота прямо сейчас: собака moxxichat_bot!"
        ),
        "card_title": "ПОДКЛЮЧАЙТЕ MOXXI 3.0 ПРЯМО СЕЙЧАС",
        "card_bullets": [
            ("🚀", "Быстрое подключение без сложной настройки"),
            ("💎", "100% бесплатные базовые функции для всех чатов"),
            ("👑", "Более 500 уникальных команд и возможностей"),
            ("🤖", "Юзернейм бота: @moxxichat_bot")
        ],
        "typing_cmd": "помощь",
        "messages": [
            {
                "sender": "Саша",
                "text": "помощь",
                "time": "12:06"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🌟 MOXXI 3.0 REVOLUTION АКТИВЕН!\n"
                    "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                    "Бот успешно работает в чате. Откройте интерактивную панель управления "
                    "или используйте команду «команды» для полного списка."
                ),
                "buttons": ["➕ Добавить в группу", "💬 Канал обновлений", "🎮 Открыть Web App"],
                "time": "12:06"
            }
        ]
    }
]

def build_telegram_frame(card_title: str, card_bullets: list, typed_text: str = "", messages: list = None):
    img = Image.new("RGB", (W, H), "#0e1621")
    draw = ImageDraw.Draw(img)

    # 1. Header Bar
    draw.rectangle([0, 0, W, 64], fill="#17212b")
    draw.line([0, 64, W, 64], fill="#232e3c", width=1)

    # Avatar circle
    draw.ellipse([18, 12, 58, 52], fill="#5b3b8c")
    draw.text((28, 16), "M", font=FONTS["header"], fill="#ffffff")

    # Titles
    draw.text((70, 14), "MOXXI", font=FONTS["header"], fill="#ffffff")
    draw.text((70, 38), "бот • официальный бот группы", font=FONTS["small"], fill="#7f91a4")

    # Right header pill
    draw.rounded_rectangle([W - 320, 15, W - 20, 49], radius=17, fill="#243447", outline="#3b526f", width=1)
    draw.text((W - 300, 21), "⚡️ MOXXI 3.0 REVOLUTION", font=FONTS["small_bold"], fill="#64b5f6")

    # 2. Bottom Input Bar
    draw.rectangle([0, H - 72, W, H], fill="#17212b")
    draw.line([0, H - 72, W, H - 72], fill="#232e3c", width=1)
    
    # Input field
    input_box = [60, H - 58, W - 90, H - 14]
    draw.rounded_rectangle(input_box, radius=22, fill="#242f3d", outline="#394a5a", width=1)
    
    # Paperclip / attach icon on the left
    draw.ellipse([20, H - 52, 48, H - 24], fill="#242f3d")
    draw.text((28, H - 47), "📎", font=FONTS["regular"], fill="#7f91a4")
    
    # Send button / Mic on the right
    draw.ellipse([W - 74, H - 54, W - 32, H - 18], fill="#5288c1" if typed_text else "#242f3d")
    draw.text((W - 61, H - 46), "➤" if typed_text else "🎙", font=FONTS["bold"], fill="#ffffff" if typed_text else "#7f91a4")

    if typed_text:
        draw.text((78, H - 48), typed_text, font=FONTS["input"], fill="#ffffff")
        # Blinking cursor
        tx = 78 + int(FONTS["input"].getlength(typed_text)) + 2
        draw.line([tx, H - 48, tx, H - 24], fill="#64b5f6", width=2)
    else:
        draw.text((78, H - 48), "Написать сообщение...", font=FONTS["input"], fill="#6c7883")

    # 3. Side Feature Showcase Card (Top Right)
    cx, cy, cw, ch = W - 440, 80, 420, 250
    draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=14, fill="#1c2533", outline="#2b5278", width=2)
    
    # Header of card
    draw.rectangle([cx + 1, cy + 1, cx + cw - 1, cy + 42], fill="#223247")
    draw.text((cx + 16, cy + 12), card_title, font=FONTS["bold"], fill="#ffd54f")
    draw.line([cx, cy + 43, cx + cw, cy + 43], fill="#2b5278", width=1)

    by = cy + 54
    for icon, text in card_bullets:
        draw.text((cx + 16, by), icon, font=FONTS["regular"], fill="#ffffff")
        draw.text((cx + 46, by + 1), text, font=FONTS["small"], fill="#e0e0e0")
        by += 44

    # 4. Chat Messages (Left area)
    if messages:
        y = 80
        for msg in messages:
            sender = msg.get("sender", "User")
            is_user = (sender == "Саша")
            text = msg.get("text", "")
            time_str = msg.get("time", "12:00")
            buttons = msg.get("buttons", [])

            lines = text.split("\n")
            max_line_len = max(len(l) for l in lines) if lines else 10
            bubble_w = min(680, max(300, max_line_len * 9 + 50))
            bubble_h = len(lines) * 22 + 34 + (len(buttons) * 42)

            if is_user:
                bx = min(W - 470 - bubble_w, 480)
                draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=12, fill="#2b5278")
                draw.text((bx + 16, y + 8), sender, font=FONTS["bold"], fill="#64b5f6")
                cy_m = y + 32
                for l in lines:
                    draw.text((bx + 16, cy_m), l, font=FONTS["regular"], fill="#ffffff")
                    cy_m += 22
                draw.text((bx + bubble_w - 65, y + bubble_h - 20), f"{time_str} ✓✓", font=FONTS["small"], fill="#90caf9")
            else:
                bx = 30
                draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=12, fill="#182533", outline="#2b5278", width=1)
                draw.text((bx + 16, y + 8), "MOXXI", font=FONTS["bold"], fill="#ce93d8")
                # БОТ badge
                draw.rounded_rectangle([bx + 85, y + 9, bx + 128, y + 25], radius=4, fill="#8e24aa")
                draw.text((bx + 92, y + 10), "БОТ", font=FONTS["small_bold"], fill="#ffffff")
                
                cy_m = y + 34
                for l in lines:
                    color = "#ffffff"
                    if "⛔️" in l or "недостаточно" in l.lower() or "проиграли" in l.lower():
                        color = "#ff5252"
                    elif "✅" in l or "победа" in l.lower() or "выигрыш" in l.lower() or "активен" in l.lower():
                        color = "#69f0ae"
                    elif "💡" in l or "баланс:" in l.lower() or "ранг:" in l.lower():
                        color = "#ffd740"
                    elif "⚔️" in l or "рулетка" in l.lower() or "штурм" in l.lower():
                        color = "#ffab40"
                    elif "•" in l or "—" in l or "┈┈" in l:
                        color = "#b0bec5"
                    draw.text((bx + 16, cy_m), l, font=FONTS["regular"], fill=color)
                    cy_m += 22

                if buttons:
                    cy_m += 6
                    btn_w = (bubble_w - 32 - (len(buttons) - 1) * 8) // len(buttons)
                    for bi, btn in enumerate(buttons):
                        btn_x = bx + 16 + bi * (btn_w + 8)
                        btn_rect = [btn_x, cy_m, btn_x + btn_w, cy_m + 32]
                        draw.rounded_rectangle(btn_rect, radius=6, fill="#242f3d", outline="#394a5a", width=1)
                        # Center button text
                        t_len = FONTS["small_bold"].getlength(btn)
                        tx_btn = btn_x + max(4, int((btn_w - t_len) / 2))
                        draw.text((tx_btn, cy_m + 7), btn, font=FONTS["small_bold"], fill="#64b5f6")

            y += bubble_h + 16

    return img

async def main():
    print("=== STARTING MOXXI 3.0 MASTER SCREENCAST BUILD ===")
    os.makedirs("screencast_temp", exist_ok=True)

    wav_files = []
    # 1. Generate Voice for all scenes with edge-tts ru-RU-SvetlanaNeural
    for i, sc in enumerate(SCENES):
        wav_path = os.path.join("screencast_temp", f"voice_{sc['id']}.wav")
        print(f"[{i+1}/{len(SCENES)}] Generating natural voice for: {sc['card_title']}...")
        await generate_voice_edge(sc["voice"], wav_path)
        wav_files.append(wav_path)

    # 2. Stitch Full Audio Track
    full_audio = "screencast_temp/full_audio.wav"
    concat_list = "screencast_temp/audio_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for w in wav_files:
            f.write(f"file '{os.path.abspath(w)}'\n")

    cmd_concat = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", full_audio
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    total_audio_dur = get_wav_duration(full_audio)
    print(f"Full audio track generated! Duration: {total_audio_dur:.1f}s ({total_audio_dur/60:.2f} min)")

    # 3. Setup Direct FFmpeg Video Encoder Pipe
    output_video = "MOXXI_3.0_GLOBAL_UPDATE.mp4"
    print(f"Starting video encoding into {output_video} via direct pipe...")

    ffmpeg_proc = subprocess.Popen([
        FFMPEG, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",
        "-i", full_audio,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_video
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Render and stream frames for each scene
    for i, sc in enumerate(SCENES):
        wav_path = wav_files[i]
        scene_dur = get_wav_duration(wav_path)
        scene_frames = int(scene_dur * FPS)

        cmd_to_type = sc.get("typing_cmd", "")
        # Phase 1: Typing text into input box (takes ~25% of scene time)
        typing_frames = min(int(scene_frames * 0.28), len(cmd_to_type) * 4)
        if typing_frames < len(cmd_to_type):
            typing_frames = len(cmd_to_type)

        messages = sc.get("messages", [])
        user_msg = messages[:1] if messages else []
        all_msgs = messages

        print(f"  Rendering scene {i+1}/{len(SCENES)}: {sc['id']} ({scene_dur:.1f}s, {scene_frames} frames)...")

        # Animate typing
        for f in range(typing_frames):
            progress = (f + 1) / float(typing_frames)
            char_count = int(progress * len(cmd_to_type))
            current_typed = cmd_to_type[:char_count]
            # While typing, no messages or previous messages
            frame = build_telegram_frame(sc["card_title"], sc["card_bullets"], current_typed, messages=user_msg)
            ffmpeg_proc.stdin.write(frame.tobytes())

        # Phase 2: User hit send, bot answers and stays on screen
        rem_frames = scene_frames - typing_frames
        full_frame = build_telegram_frame(sc["card_title"], sc["card_bullets"], "", messages=all_msgs)
        full_bytes = full_frame.tobytes()

        for _ in range(rem_frames):
            ffmpeg_proc.stdin.write(full_bytes)

    # Close pipe and finalize
    ffmpeg_proc.stdin.close()
    ffmpeg_proc.wait()

    if os.path.exists(output_video):
        size_mb = os.path.getsize(output_video) / (1024 * 1024)
        print(f"=== SUCCESS! Video rendered: {output_video} ({size_mb:.2f} MB, {total_audio_dur:.1f}s) ===")
    else:
        print("ERROR: Output video was not created!")

if __name__ == "__main__":
    asyncio.run(main())
