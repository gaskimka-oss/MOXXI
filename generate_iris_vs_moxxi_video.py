import os
import re
import sys
import asyncio
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
import edge_tts

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SCENES_DATA = [
    {
        "id": "scene1",
        "image": "img_banner_main.jpg",
        "audio": "vs_scene1.mp3",
        "tag": "MOXXI 2.0 VS IRIS • ВСТУПЛЕНИЕ",
        "title": "ПОЧЕМУ ИРИС УСТАРЕЛ НА 6 ЛЕТ?",
        "desc": "Сравнение: древний чат-менеджер 2018 года против современной экосистемы 2026",
        "iris_bad": "Ирис: скучный текст, старые команды, ноль ИИ",
        "moxxi_good": "Мокси 2.0: живая нейросеть, RPG, кланы и безопасность",
        "pan": "zoom_in",
        "voice_text": "Привет, друзья! Если вы управляете беседой в Телеграме, вы наверняка знаете бота Ирис. Но давайте честно: Ирис появился много лет назад и безнадёжно застрял в прошлом. В нём скучные текстовые команды, старые механики и ноль современных технологий. А теперь взгляните на Мокси два ноль. Это не просто бот для мутов, это грандиозная нейросетевая, игровая и социальная экосистема, где общаться и играть в разы интереснее! Сейчас мы детально пройдёмся по каждой команде, которой у Ириса нет даже близко!"
    },
    {
        "id": "scene2",
        "image": "img_sec_social.jpg",
        "audio": "vs_scene2.mp3",
        "tag": "НЕЙРОСЕТИ • GOOGLE GEMINI AI",
        "title": "MOXXI AI ENGINE VS ПУСТОТА В ИРИСЕ",
        "desc": "Голосовые в текст (гс текст) • Диалоги (ии) • Умные анонсы • Явка на кнопках",
        "iris_bad": "Ирис: 0% нейросетей, глупый статичный бот",
        "moxxi_good": "Мокси: Gemini 2.5, перевод ГС в текст, умные сценарии",
        "pan": "pan_right",
        "voice_text": "Пункт первый — искусственный интеллект. В Ирисе нейросетей нет вообще. В Мокси встроен мощный движок Google Gemini! Команда «ии» превращает бота в живого собеседника с дерзким характером. Команда «гс текст» мгновенно переводит голосовые сообщения и видео-кружочки в читаемый текст. А команда «ии анонс» сама пишет шикарные посты для съёмок и турниров с красивым эмодзи-временем и интерактивной явкой на кнопках Буду, Не смогу, Опоздаю! Плюс полноценный Telegram WebApp прямо внутри мессенджера!"
    },
    {
        "id": "scene3",
        "image": "img_sec_moderation.jpg",
        "audio": "vs_scene3.mp3",
        "tag": "БЕЗОПАСНОСТЬ 2.0 • АНТИ-СЛИВ",
        "title": "ЗАЩИТА БЕСЕДЫ VS СЛИВЫ ИРИСА",
        "desc": "Лимиты наказаний • Капча 'Я человек' • Антирейд • ЧС чата • 2FA админам",
        "iris_bad": "Ирис: модератор может слить весь чат за пару минут",
        "moxxi_good": "Мокси: Анти-слив блокирует кики/баны младшему составу",
        "pan": "zoom_in",
        "voice_text": "Второй огромный плюс — абсолютная безопасность. В Ирисе обиженный модератор может слить весь чат за пару минут. В Мокси это физически невозможно! У нас внедрён Анти-слив: у стажёров и младших модераторов кики и баны заблокированы намертво, а муты ограничены тремя в десять минут. Вход защищён кнопкой-капчей «Я человек», которая уничтожает бот-атаки. Команда «плюс фильтр» включает автонаказание за запрещённые слова, а команды «антирейд», «щит» и «блок медиа» защищают чат от спама новичков. Также есть тайная слежка за подозрительными юзерами и двухфакторка для админов!"
    },
    {
        "id": "scene4",
        "image": "img_sec_economy.jpg",
        "audio": "vs_scene4.mp3",
        "tag": "ЭКОНОМИКА 2.0 • ИМПЕРИЯ БИЗНЕСОВ",
        "title": "ЖИВАЯ КАРЬЕРА VS СКУЧНЫЕ МЕШКИ ИРИСА",
        "desc": "6 профессий по LVL • 30 бизнесов • Депозит +3% • Крипта MoxxiCoin • Чеки",
        "iris_bad": "Ирис: примитивная передача мешков золота",
        "moxxi_good": "Мокси: 6 профессий, 30 предприятий, банковский депозит",
        "pan": "zoom_out",
        "voice_text": "Переходим к экономике. В Ирисе всё уныло — передача мешков и простая ферма. В Мокси — полноценная финансовая жизнь! У нас есть карьерная лестница по команде «работа»: Дворник, Курьер, Бариста, Программист, Банкир и Инвестор, открывающиеся по уровням. Тридцать предприятий с прокачкой до сотого левела и партнёрством. Банковский депозит приносит плюс три процента чистой прибыли каждые сутки. Есть платёжные чеки для красивых переводов, своя биржа криптовалюты MoxxiCoin с живым курсом и чат-лотерея!"
    },
    {
        "id": "scene5",
        "image": "img_sec_settings.jpg",
        "audio": "vs_scene5.mp3",
        "tag": "ВЫСЛУГА ЛЕТ • ВЕТЕРАНЫ БЕСЕДЫ",
        "title": "НАГРАДЫ ЗА ВЕРНОСТЬ ЧАТУ",
        "desc": "7 титулов от Гостя до Хранителя • Ежедневный бонус до +2,500 монет • Топ стаж",
        "iris_bad": "Ирис: стаж участника в чате не даёт абсолютно ничего",
        "moxxi_good": "Мокси: 7 титулов верности и ежедневная выплата за стаж",
        "pan": "pan_right",
        "voice_text": "В Ирисе твой стаж не ценится. В Мокси преданность чату вознаграждается каждый день! Бот считает, сколько дней ты находишься именно в этой группе. Команда «стаж» показывает твоё почётное звание: от Гостя и Старожила до Легенды чата и Вечного Хранителя. За выслугу лет доступен ежедневный денежный бонус до двух с половиной тысяч монет! А команда «топ стаж» собирает зал славы долгожителей беседы. Твой стаж гордо виден прямо в профиле!"
    },
    {
        "id": "scene6",
        "image": "moxxi_scene4_boss_1791698456705.jpg",
        "audio": "vs_scene6.mp3",
        "tag": "MMORPG • БОИ • КЛАНОВЫЕ ВОЙНЫ",
        "title": "РЕЙД-БОССЫ И ГОРОДСКИЕ ЗАХВАТЫ",
        "desc": "Боссы с фазами ярости • Данжи • Рыбалка & Крафт • Питомцы • Захват районов",
        "iris_bad": "Ирис: унылая текстовая дуэль без графики и экшена",
        "moxxi_good": "Мокси: титанические боссы, подземелья, верстак и захваты",
        "pan": "zoom_in",
        "voice_text": "Геймплей в Мокси — на уровне настоящих RPG! Пока в Ирисе кидают скучную команду «дуэль», у нас проходят масштабные рейды на Боссов с фазами ярости и контратаками. Игроки штурмуют Подземелья, ловят восемь видов рыбы, куют броню на верстаке и прокачивают боевых питомцев. А для кланов есть война за город: команда «районы» позволяет захватывать целые кварталы города за пассивный доход в казну клана и заключать дипломатические военные альянсы!"
    },
    {
        "id": "scene7",
        "image": "moxxi_scene2_casino_1791698428497.jpg",
        "audio": "vs_scene7.mp3",
        "tag": "СООБЩЕСТВО • ПРЕДЛОЖИТЬ ИДЕЮ",
        "title": "МЫ РАЗВИВАЕМСЯ ВМЕСТЕ С ВАМИ!",
        "desc": "Стена профиля • Био • Таро • Свадьбы • Команда (предложить) для каждого игрока!",
        "iris_bad": "Ирис: разработчики игнорируют идеи пользователей",
        "moxxi_good": "Мокси: команда (предложить) — пиши идею и мы внедрим её!",
        "pan": "zoom_out",
        "voice_text": "И наконец, самое главное. В Мокси потрясающая атмосфера: росписи на стене профиля, био, комплименты, свадьбы, расклады Таро и быстрое казино на кнопках. Но главное отличие от Ириса — мы открыты для сообщества! Любой игрок может написать команду «предложить», и мы регулярно воплощаем ваши идеи в жизнь. Ирис годами не обновляется, а Мокси растёт каждый день! Переходите на Мокси два ноль и ощутите разницу сами!"
    }
]

async def generate_voiceovers():
    print("=== ГЕНЕРАЦИЯ ГОЛОСОВОЙ ОЗВУЧКИ ЧЕРЕЗ EDGE-TTS ===")
    for sc in SCENES_DATA:
        audio_path = sc["audio"]
        if os.path.exists(audio_path):
            print(f"[{sc['id']}] Аудио уже существует: {audio_path}")
            continue
        print(f"[{sc['id']}] Синтез озвучки...")
        comm = edge_tts.Communicate(sc["voice_text"], 'ru-RU-SvetlanaNeural', rate='+6%')
        await comm.save(audio_path)
        print(f"[{sc['id']}] Готово: {audio_path}")

def get_audio_duration(audio_file):
    cmd = [FFMPEG_EXE, "-i", audio_file]
    p = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", p.stderr)
    if m:
        h, mn, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return h * 3600 + mn * 60 + s
    return 16.0

def create_ui_overlay(width, height, tag, title, desc, iris_bad, moxxi_good, progress, scene_num, total_scenes):
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    font_reg_path = r"C:\Windows\Fonts\arial.ttf"

    font_tag = ImageFont.truetype(font_bold_path, 17)
    font_title = ImageFont.truetype(font_bold_path, 32)
    font_desc = ImageFont.truetype(font_reg_path, 20)
    font_vs = ImageFont.truetype(font_bold_path, 19)
    font_wm = ImageFont.truetype(font_bold_path, 16)

    # 1. Верхний бейдж
    badge_x, badge_y = 40, 36
    draw.rounded_rectangle([badge_x, badge_y, badge_x + 380, badge_y + 36], radius=8, fill=(15, 10, 30, 210), outline=(255, 45, 150, 200), width=1)
    draw.ellipse([badge_x + 14, badge_y + 13, badge_x + 24, badge_y + 23], fill=(0, 255, 200, 255))
    draw.text((badge_x + 34, badge_y + 8), tag, font=font_tag, fill=(255, 255, 255, 255))

    # Водяной знак справа
    wm_text = f"@moxxichat_bot  [{scene_num}/{total_scenes}]"
    draw.rounded_rectangle([width - 250, badge_y, width - 40, badge_y + 36], radius=8, fill=(15, 10, 30, 200), outline=(0, 220, 255, 160), width=1)
    draw.text((width - 235, badge_y + 8), wm_text, font=font_wm, fill=(0, 230, 255, 255))

    # 2. Нижняя стеклянная плашка
    banner_h = 175
    banner_top = height - banner_h
    draw.rectangle([0, banner_top, width, height], fill=(10, 8, 22, 230))
    draw.line([(0, banner_top), (width, banner_top)], fill=(255, 0, 128, 220), width=2)

    # Заголовок
    draw.text((40, banner_top + 14), title, font=font_title, fill=(255, 240, 80, 255))
    # Описание
    draw.text((40, banner_top + 56), desc, font=font_desc, fill=(220, 230, 245, 240))

    # Сравнение: Ирис vs Мокси
    card_y = banner_top + 92
    # Ирис бейдж (красный)
    draw.rounded_rectangle([40, card_y, 40 + 560, card_y + 34], radius=6, fill=(50, 10, 15, 200), outline=(255, 60, 60, 180), width=1)
    draw.text((50, card_y + 6), f"❌ {iris_bad}", font=font_vs, fill=(255, 120, 120, 255))

    # Мокси бейдж (зелёно-голубой)
    draw.rounded_rectangle([620, card_y, 620 + 620, card_y + 34], radius=6, fill=(10, 45, 35, 200), outline=(0, 255, 160, 180), width=1)
    draw.text((630, card_y + 6), f"🔥 {moxxi_good}", font=font_vs, fill=(80, 255, 180, 255))

    # Индикатор прогресса
    draw.rectangle([0, height - 6, width, height], fill=(20, 15, 35, 255))
    prog_w = int(width * max(0.0, min(1.0, progress)))
    if prog_w > 0:
        draw.rectangle([0, height - 6, prog_w, height], fill=(0, 255, 200, 255))

    return overlay

def render_scene(scene, output_video, scene_num, total_scenes, width=1280, height=720, fps=30):
    audio_dur = get_audio_duration(scene["audio"])
    total_duration = audio_dur + 0.4
    total_frames = int(total_duration * fps)

    img = cv2.imread(scene["image"])
    if img is None:
        raise ValueError(f"Cannot read {scene['image']}")

    img_h, img_w = img.shape[:2]
    temp_silent = f"temp_{scene['id']}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_silent, fourcc, fps, (width, height))

    pan_type = scene.get("pan", "zoom_in")

    for f in range(total_frames):
        t = f / float(total_frames)

        if pan_type == "zoom_in":
            zoom = 1.0 + 0.12 * t
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            drift_x = int((img_w - crop_w) * 0.1 * np.sin(t * np.pi))
            x1 = max(0, min(img_w - crop_w, (img_w - crop_w) // 2 + drift_x))
            y1 = max(0, min(img_h - crop_h, (img_h - crop_h) // 2))
        elif pan_type == "zoom_out":
            zoom = 1.12 - 0.12 * t
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            x1 = max(0, min(img_w - crop_w, (img_w - crop_w) // 2))
            y1 = max(0, min(img_h - crop_h, (img_h - crop_h) // 2))
        else: # pan_right
            zoom = 1.06
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            shift_x = int((img_w - crop_w) * t)
            x1 = max(0, min(img_w - crop_w, shift_x))
            y1 = max(0, min(img_h - crop_h, (img_h - crop_h) // 2))

        cropped = img[y1:y1+crop_h, x1:x1+crop_w]
        frame = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)

        # Конвертируем в PIL для красивой графики
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_frame = Image.fromarray(frame_rgb).convert("RGBA")

        overlay = create_ui_overlay(
            width, height,
            scene["tag"], scene["title"], scene["desc"],
            scene["iris_bad"], scene["moxxi_good"],
            t, scene_num, total_scenes
        )

        pil_frame.alpha_composite(overlay)
        res_bgr = cv2.cvtColor(np.array(pil_frame.convert("RGB")), cv2.COLOR_RGB2BGR)

        writer.write(res_bgr)

    writer.release()

    # Сведение аудио + видео
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", temp_silent,
        "-i", scene["audio"],
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_video
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(temp_silent):
        os.remove(temp_silent)
    print(f"[{scene['id']}] Видеоряд смонтирован: {output_video}")

def concat_all_scenes(scene_videos, final_output):
    print("=== ОБЪЕДИНЕНИЕ ВСЕХ СЦЕН В ИТОГОВЫЙ ВИДЕОРОЛИК ===")
    list_file = "concat_scenes.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for sv in scene_videos:
            f.write(f"file '{os.path.abspath(sv)}'\n")

    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        final_output
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(list_file):
        os.remove(list_file)
    print(f"🎉 ИТОГОВЫЙ ВИДЕОРОЛИК УСПЕШНО СОЗДАН: {final_output}")

async def main():
    await generate_voiceovers()

    scene_videos = []
    total = len(SCENES_DATA)
    for idx, sc in enumerate(SCENES_DATA, start=1):
        out_v = f"v_part_{sc['id']}.mp4"
        print(f"\n--- РЕНДЕРИНГ СЦЕНЫ {idx}/{total}: {sc['title']} ---")
        render_scene(sc, out_v, idx, total)
        scene_videos.append(out_v)

    final_video = "moxxi_vs_iris_comparison.mp4"
    concat_all_scenes(scene_videos, final_video)

if __name__ == "__main__":
    asyncio.run(main())
