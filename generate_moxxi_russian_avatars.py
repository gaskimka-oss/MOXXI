"""Генератор 5 официальных аватарок в стиле Moxxi (Cyberpunk/Casino/Neon),
полностью на русском языке, с чистым оригинальным артом и насыщенными неоновыми цветами
(без слепящего белого текста и без инородных наклеек).
Разрешение: 1024x1024.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SOURCE_IMG = r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\.user_uploaded\media_1791617263660_0b6a1b1e.png"
OUTPUT_DIR = r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9"
DESKTOP_AVATARS_DIR = r"c:\Users\eiema\OneDrive\Desktop\бот2.0\avatars"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DESKTOP_AVATARS_DIR, exist_ok=True)

FONT_PATH = r"C:\Windows\Fonts\segoeuib.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"


def get_base_1024():
    """Загружает исходный арт, обрезает черную полосу снизу и масштабирует до 1024x1024."""
    im = Image.open(SOURCE_IMG).convert("RGBA")
    im_sq = im.crop((0, 0, 654, 654))
    im_1024 = im_sq.resize((1024, 1024), Image.Resampling.LANCZOS)

    # Идеально и бесшовно убираем старую англоязычную надпись «TELEGRAM BOT»
    # Сохраняем нетронутой нижнюю неоновую дугу и верхние буквы MOXXI
    patch = Image.new("RGBA", im_1024.size, (8, 2, 24, 255))
    mask = Image.new("L", im_1024.size, 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([280, 869, 744, 914], radius=4, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.5))
    im_1024.paste(patch, (0, 0), mask)
    return im_1024


def draw_neon_text(base_img, text, font_size, text_color, glow_color, letter_spacing=3, cy=892):
    """Рисует неоновый текст с мягким многослойным свечением и межбуквенным расстоянием."""
    font = ImageFont.truetype(FONT_PATH, font_size)
    dummy_draw = ImageDraw.Draw(base_img)
    char_widths = [dummy_draw.textlength(ch, font=font) for ch in text]
    total_w = sum(char_widths) + (len(text) - 1) * letter_spacing

    start_x = int(512 - total_w / 2)
    bbox = font.getbbox("А")
    h = bbox[3] - bbox[1]
    y = int(cy - h / 2)

    # 1. Широкое мягкое неоновое свечение (Gaussian Blur)
    glow_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_layer)
    curr_x = start_x
    for i, ch in enumerate(text):
        gdraw.text((curr_x, y), ch, font=font, fill=glow_color + (255,))
        curr_x += int(char_widths[i] + letter_spacing)

    glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=7))
    glow_tight = glow_layer.filter(ImageFilter.GaussianBlur(radius=2))

    # 2. Основной слой текста (чистый насыщенный неоновый цвет)
    text_layer = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    curr_x = start_x
    for i, ch in enumerate(text):
        tdraw.text((curr_x, y), ch, font=font, fill=text_color + (255,))
        curr_x += int(char_widths[i] + letter_spacing)

    # Композитинг
    res = Image.alpha_composite(base_img, glow_blurred)
    res = Image.alpha_composite(res, glow_tight)
    res = Image.alpha_composite(res, text_layer)
    return res


def save_avatar(im, filename):
    p1 = os.path.join(OUTPUT_DIR, filename)
    p2 = os.path.join(DESKTOP_AVATARS_DIR, filename)
    im.save(p1, "PNG")
    im.save(p2, "PNG")
    print(f"Saved: {filename}")


# 1. АВАТАРКА ГЛАВНОГО БОТА (Электрический Неоновый Циан)
def make_bot_avatar():
    im = get_base_1024()
    im = draw_neon_text(
        im,
        "ГЛАВНЫЙ БОТ",
        font_size=32,
        text_color=(0, 240, 255),
        glow_color=(0, 160, 255),
        letter_spacing=5,
    )
    save_avatar(im, "moxxistyle_1_bot.png")


# 2. АВАТАРКА ГРУППЫ ИДЕЙ (Неоновая Маджента / Фиолетовый)
def make_ideas_avatar():
    im = get_base_1024()
    im = draw_neon_text(
        im,
        "ИДЕИ И ПРЕДЛОЖЕНИЯ",
        font_size=24,
        text_color=(255, 60, 210),
        glow_color=(210, 0, 255),
        letter_spacing=2,
    )
    save_avatar(im, "moxxistyle_2_ideas.png")


# 3. АВАТАРКА ЧАТА ДЛЯ ОБЩЕНИЯ (Неоновый Мятный Циан)
def make_chat_avatar():
    im = get_base_1024()
    im = draw_neon_text(
        im,
        "ЧАТ СООБЩЕСТВА",
        font_size=28,
        text_color=(0, 245, 230),
        glow_color=(0, 180, 255),
        letter_spacing=3,
    )
    save_avatar(im, "moxxistyle_3_chat.png")


# 4. АВАТАРКА ОТЗЫВОВ И РЕЙТИНГА (Благородное Неоновое Золото)
def make_reviews_avatar():
    im = get_base_1024()
    im = draw_neon_text(
        im,
        "ОТЗЫВЫ И РЕЙТИНГ",
        font_size=26,
        text_color=(255, 215, 0),
        glow_color=(255, 140, 0),
        letter_spacing=3,
    )
    save_avatar(im, "moxxistyle_4_reviews.png")


# 5. АВАТАРКА ТЕХ. ПОДДЕРЖКИ (Изумрудно-Неоновый)
def make_support_avatar():
    im = get_base_1024()
    im = draw_neon_text(
        im,
        "ТЕХ. ПОДДЕРЖКА",
        font_size=28,
        text_color=(0, 255, 180),
        glow_color=(0, 190, 140),
        letter_spacing=3,
    )
    save_avatar(im, "moxxistyle_5_support.png")


if __name__ == "__main__":
    make_bot_avatar()
    make_ideas_avatar()
    make_chat_avatar()
    make_reviews_avatar()
    make_support_avatar()
    print("All 5 clean Moxxi-Style Russian avatars created successfully!")
