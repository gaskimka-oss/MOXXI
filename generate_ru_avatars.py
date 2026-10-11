"""Генератор 5 стильных неоновых аватарок на русском языке для экосистемы Moxxi Bot.
Разрешение: 1024x1024 (идеально для аватарок Telegram).
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_PATH = r"C:\Windows\Fonts\segoeuib.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"

def get_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def draw_glow_text(draw, pos, text, font, fill_color, glow_color, glow_radius=8):
    x, y = pos
    # multi-pass shadow/glow
    for offset in range(glow_radius, 0, -2):
        for dx in (-offset, 0, offset):
            for dy in (-offset, 0, offset):
                if dx == 0 and dy == 0:
                    continue
                alpha = int(80 / (offset + 1))
                c = glow_color + (alpha,)
                draw.text((x + dx, y + dy), text, font=font, fill=c)
    draw.text((x, y), text, font=font, fill=fill_color + (255,))

def create_base_canvas(theme_color_primary, theme_color_secondary):
    # Dark cyberpunk background with radial gradient & tech accents
    img = Image.new("RGBA", (1024, 1024), (10, 8, 20, 255))
    draw = ImageDraw.Draw(img)

    # Radial gradient glow in the center
    center_x, center_y = 512, 450
    for r in range(480, 0, -12):
        alpha = int(55 * (1 - r / 480))
        color = theme_color_primary if r > 200 else theme_color_secondary
        draw.ellipse([center_x - r, center_y - r, center_x + r, center_y + r],
                     fill=color + (alpha,))

    # Cyber grid lines faint
    for gy in range(0, 1024, 64):
        draw.line([(0, gy), (1024, gy)], fill=(40, 30, 70, 35), width=1)
    for gx in range(0, 1024, 64):
        draw.line([(gx, 0), (gx, 1024)], fill=(40, 30, 70, 35), width=1)

    # Outer cyberpunk glowing rounded frame
    pad = 48
    draw.rounded_rectangle([pad, pad, 1024 - pad, 1024 - pad], radius=60,
                           outline=theme_color_primary + (180,), width=4)
    draw.rounded_rectangle([pad + 12, pad + 12, 1024 - pad - 12, 1024 - pad - 12], radius=50,
                           outline=theme_color_secondary + (100,), width=2)

    # Tech corners
    c_len = 50
    for cx, cy in [(pad, pad), (1024 - pad, pad), (pad, 1024 - pad), (1024 - pad, 1024 - pad)]:
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=theme_color_primary + (255,))

    return img, draw

# 1. MOXXI БОТ (Главный бот)
def make_bot_avatar():
    img, draw = create_base_canvas((255, 0, 140), (160, 0, 255))
    
    # Diamond / Octagon shield in center
    cx, cy = 512, 410
    rad = 220
    poly = [
        (cx, cy - rad), (cx + rad*0.7, cy - rad*0.7),
        (cx + rad, cy), (cx + rad*0.7, cy + rad*0.7),
        (cx, cy + rad), (cx - rad*0.7, cy + rad*0.7),
        (cx - rad, cy), (cx - rad*0.7, cy - rad*0.7)
    ]
    draw.polygon(poly, fill=(20, 15, 38, 240), outline=(255, 0, 140, 255))
    draw.polygon([(x*0.9 + cx*0.1, y*0.9 + cy*0.1) for x, y in poly],
                 outline=(0, 240, 255, 200), width=3)

    # Crown / Star icon in center
    draw.polygon([(cx, cy - 110), (cx + 50, cy - 40), (cx + 120, cy - 50),
                  (cx + 70, cy + 30), (cx + 90, cy + 110), (cx, cy + 60),
                  (cx - 90, cy + 110), (cx - 70, cy + 30), (cx - 120, cy - 50),
                  (cx - 50, cy - 40)],
                 fill=(255, 215, 0, 255), outline=(255, 255, 255, 255))

    # Russian text
    f_title = get_font(72)
    f_sub = get_font(38)
    f_moxxi = get_font(52)

    t_moxxi = "MOXXI BOT"
    w_moxxi = draw.textlength(t_moxxi, font=f_moxxi)
    draw_glow_text(draw, (cx - w_moxxi / 2, 700), t_moxxi, f_moxxi, (255, 0, 140), (255, 50, 180), 8)

    t_ru = "ГЛАВНЫЙ БОТ"
    w_ru = draw.textlength(t_ru, font=f_title)
    draw_glow_text(draw, (cx - w_ru / 2, 780), t_ru, f_title, (255, 255, 255), (160, 0, 255), 10)

    t_sub = "ИГРЫ • КАЗИНО • КЛАНЫ • ОБЩЕНИЕ"
    w_sub = draw.textlength(t_sub, font=f_sub)
    draw.text((cx - w_sub / 2, 880), t_sub, font=f_sub, fill=(0, 240, 255, 220))

    path = os.path.join(OUTPUT_DIR, "avatar_1_moxxi_bot_ru.png")
    img.save(path, "PNG")
    print(f"Saved: {path}")

# 2. ИДЕИ И ПРЕДЛОЖЕНИЯ
def make_ideas_avatar():
    img, draw = create_base_canvas((180, 0, 255), (255, 0, 200))
    cx, cy = 512, 400

    # Glowing Lightbulb Emblem
    # Bulb top
    draw.ellipse([cx - 130, cy - 160, cx + 130, cy + 60], fill=(25, 15, 45, 240), outline=(255, 0, 220, 255), width=6)
    # Bulb base
    draw.polygon([(cx - 70, cy + 30), (cx + 70, cy + 30), (cx + 50, cy + 120), (cx - 50, cy + 120)],
                 fill=(40, 25, 70, 255), outline=(0, 240, 255, 255), width=4)
    # Thread lines
    for ly in [cy + 60, cy + 85, cy + 110]:
        draw.line([(cx - 45, ly), (cx + 45, ly)], fill=(255, 215, 0, 255), width=5)

    # Filament glowing inside
    draw.arc([cx - 60, cy - 80, cx + 60, cy + 10], start=180, end=0, fill=(255, 255, 100, 255), width=8)
    draw.line([(cx - 40, cy - 80), (cx - 20, cy - 10)], fill=(255, 255, 200, 255), width=6)
    draw.line([(cx + 40, cy - 80), (cx + 20, cy - 10)], fill=(255, 255, 200, 255), width=6)

    # Sparks/Rays
    for angle in [-140, -110, -70, -40]:
        rad = math.radians(angle)
        x1 = cx + math.cos(rad) * 160
        y1 = cy - 50 + math.sin(rad) * 160
        x2 = cx + math.cos(rad) * 210
        y2 = cy - 50 + math.sin(rad) * 210
        draw.line([(x1, y1), (x2, y2)], fill=(255, 230, 0, 230), width=6)

    # Text
    f_badge = get_font(42)
    f_main = get_font(68)
    f_sub = get_font(36)

    t_badge = "💡 MOXXI ИДЕИ"
    w_b = draw.textlength(t_badge, font=f_badge)
    draw_glow_text(draw, (cx - w_b / 2, 700), t_badge, f_badge, (255, 220, 50), (255, 120, 0), 8)

    t_main = "ПРЕДЛОЖЕНИЯ"
    w_m = draw.textlength(t_main, font=f_main)
    draw_glow_text(draw, (cx - w_m / 2, 780), t_main, f_main, (255, 255, 255), (180, 0, 255), 10)

    t_sub = "ГОЛОСОВАНИЕ • УЛУЧШЕНИЯ • ОБНОВЛЕНИЯ"
    w_s = draw.textlength(t_sub, font=f_sub)
    draw.text((cx - w_s / 2, 880), t_sub, font=f_sub, fill=(255, 100, 230, 220))

    path = os.path.join(OUTPUT_DIR, "avatar_2_ideas_group_ru.png")
    img.save(path, "PNG")
    print(f"Saved: {path}")

# 3. ЧАТ И ОБЩЕНИЕ
def make_chat_avatar():
    img, draw = create_base_canvas((0, 210, 255), (255, 0, 180))
    cx, cy = 512, 400

    # Two glowing speech bubbles
    # Bubble 1 (Cyan)
    draw.rounded_rectangle([cx - 180, cy - 140, cx + 80, cy + 20], radius=40,
                           fill=(15, 35, 60, 240), outline=(0, 230, 255, 255), width=6)
    draw.polygon([(cx - 100, cy + 20), (cx - 150, cy + 80), (cx - 50, cy + 20)],
                 fill=(15, 35, 60, 255), outline=(0, 230, 255, 255))
    draw.line([(cx - 95, cy + 20), (cx - 55, cy + 20)], fill=(15, 35, 60, 255), width=8)

    # Faint sound wave in bubble 1
    for i, h in enumerate([25, 45, 65, 35, 55, 20]):
        bx = cx - 140 + i * 35
        draw.rounded_rectangle([bx, cy - 60 - h//2, bx + 12, cy - 60 + h//2], radius=6,
                               fill=(0, 240, 255, 220))

    # Bubble 2 (Pink/Magenta)
    draw.rounded_rectangle([cx - 60, cy - 30, cx + 190, cy + 120], radius=35,
                           fill=(50, 15, 45, 240), outline=(255, 0, 160, 255), width=5)
    draw.polygon([(cx + 90, cy + 120), (cx + 150, cy + 175), (cx + 130, cy + 120)],
                 fill=(50, 15, 45, 255), outline=(255, 0, 160, 255))
    draw.line([(cx + 95, cy + 120), (cx + 125, cy + 120)], fill=(50, 15, 45, 255), width=8)

    # Smiley/heart in bubble 2
    f_icon = get_font(48)
    draw.text((cx + 20, cy + 25), "💬 ❤️", font=f_icon, fill=(255, 255, 255, 255))

    # Text
    f_badge = get_font(44)
    f_main = get_font(68)
    f_sub = get_font(36)

    t_badge = "MOXXI СООБЩЕСТВО"
    w_b = draw.textlength(t_badge, font=f_badge)
    draw_glow_text(draw, (cx - w_b / 2, 700), t_badge, f_badge, (0, 240, 255), (0, 150, 255), 8)

    t_main = "ЧАТ И ОБЩЕНИЕ"
    w_m = draw.textlength(t_main, font=f_main)
    draw_glow_text(draw, (cx - w_m / 2, 780), t_main, f_main, (255, 255, 255), (255, 0, 160), 10)

    t_sub = "ДРУЗЬЯ • КЛАНЫ • ЗНАКОМСТВА • ТЕМЫ"
    w_s = draw.textlength(t_sub, font=f_sub)
    draw.text((cx - w_s / 2, 880), t_sub, font=f_sub, fill=(0, 230, 255, 220))

    path = os.path.join(OUTPUT_DIR, "avatar_3_chat_group_ru.png")
    img.save(path, "PNG")
    print(f"Saved: {path}")

# 4. ОТЗЫВЫ И РЕЙТИНГ
def make_reviews_avatar():
    img, draw = create_base_canvas((255, 190, 0), (255, 0, 120))
    cx, cy = 512, 380

    # Golden Shield
    sw, sh = 190, 220
    shield_poly = [
        (cx - sw, cy - sh*0.7), (cx + sw, cy - sh*0.7),
        (cx + sw, cy + sh*0.2), (cx, cy + sh),
        (cx - sw, cy + sh*0.2)
    ]
    draw.polygon(shield_poly, fill=(25, 20, 10, 245), outline=(255, 200, 0, 255), width=6)
    draw.polygon([(x*0.88 + cx*0.12, y*0.88 + cy*0.12) for x, y in shield_poly],
                 outline=(255, 80, 160, 200), width=3)

    # 5 Big Golden Stars across center
    star_positions = [
        (cx - 130, cy - 20, 28),
        (cx - 65, cy - 45, 34),
        (cx, cy - 60, 44),
        (cx + 65, cy - 45, 34),
        (cx + 130, cy - 20, 28),
    ]
    for sx, sy, srad in star_positions:
        pts = []
        for i in range(10):
            r = srad if i % 2 == 0 else srad * 0.45
            ang = math.radians(i * 36 - 90)
            pts.append((sx + r * math.cos(ang), sy + r * math.sin(ang)))
        draw.polygon(pts, fill=(255, 215, 0, 255), outline=(255, 255, 200, 255), width=2)

    # 5.0 Rating Text on Shield
    f_rate = get_font(52)
    t_rate = "5.0 ★★★★★"
    w_r = draw.textlength(t_rate, font=f_rate)
    draw.text((cx - w_r / 2, cy + 40), t_rate, font=f_rate, fill=(255, 235, 150, 255))

    # Text
    f_badge = get_font(44)
    f_main = get_font(68)
    f_sub = get_font(36)

    t_badge = "⭐ MOXXI ОТЗЫВЫ"
    w_b = draw.textlength(t_badge, font=f_badge)
    draw_glow_text(draw, (cx - w_b / 2, 700), t_badge, f_badge, (255, 215, 0), (255, 120, 0), 8)

    t_main = "ОТЗЫВЫ И РЕЙТИНГ"
    w_m = draw.textlength(t_main, font=f_main)
    draw_glow_text(draw, (cx - w_m / 2, 780), t_main, f_main, (255, 255, 255), (255, 180, 0), 10)

    t_sub = "ОЦЕНКИ • ЧЕСТНЫЕ ОТЗЫВЫ • ДОВЕРИЕ"
    w_s = draw.textlength(t_sub, font=f_sub)
    draw.text((cx - w_s / 2, 880), t_sub, font=f_sub, fill=(255, 200, 50, 220))

    path = os.path.join(OUTPUT_DIR, "avatar_4_reviews_group_ru.png")
    img.save(path, "PNG")
    print(f"Saved: {path}")

# 5. ТЕХПОДДЕРЖКА 24/7
def make_support_avatar():
    img, draw = create_base_canvas((0, 255, 180), (0, 150, 255))
    cx, cy = 512, 390

    # Futuristic Headset & Lifebelt / Tech Shield
    # Outer ring
    draw.ellipse([cx - 160, cy - 160, cx + 160, cy + 160], fill=(10, 25, 30, 240),
                 outline=(0, 255, 180, 255), width=6)
    draw.ellipse([cx - 130, cy - 130, cx + 130, cy + 130],
                 outline=(0, 180, 255, 180), width=3)

    # Cross / Lifebuoy / Medical-Help symbol
    cr = 65
    draw.rectangle([cx - 20, cy - cr, cx + 20, cy + cr], fill=(0, 255, 180, 255))
    draw.rectangle([cx - cr, cy - 20, cx + cr, cy + 20], fill=(0, 255, 180, 255))

    # Headphone arc over top
    draw.arc([cx - 190, cy - 200, cx + 190, cy + 100], start=190, end=350,
             fill=(0, 240, 255, 255), width=16)
    # Ear pads
    draw.rounded_rectangle([cx - 205, cy - 60, cx - 175, cy + 50], radius=12,
                           fill=(0, 255, 180, 255), outline=(255, 255, 255, 255), width=3)
    draw.rounded_rectangle([cx + 175, cy - 60, cx + 205, cy + 50], radius=12,
                           fill=(0, 255, 180, 255), outline=(255, 255, 255, 255), width=3)
    # Mic boom
    draw.arc([cx - 100, cy + 10, cx + 190, cy + 160], start=40, end=130,
             fill=(0, 255, 220, 255), width=8)
    draw.ellipse([cx - 30, cy + 120, cx + 10, cy + 150], fill=(255, 50, 100, 255))

    # Text
    f_badge = get_font(44)
    f_main = get_font(68)
    f_sub = get_font(36)

    t_badge = "🆘 СЛУЖБА ПОДДЕРЖКИ"
    w_b = draw.textlength(t_badge, font=f_badge)
    draw_glow_text(draw, (cx - w_b / 2, 700), t_badge, f_badge, (0, 255, 180), (0, 180, 255), 8)

    t_main = "ТЕХПОДДЕРЖКА 24/7"
    w_m = draw.textlength(t_main, font=f_main)
    draw_glow_text(draw, (cx - w_m / 2, 780), t_main, f_main, (255, 255, 255), (0, 255, 180), 10)

    t_sub = "ТИКЕТЫ • ПОМОЩЬ • ИИ-АССИСТЕНТ"
    w_s = draw.textlength(t_sub, font=f_sub)
    draw.text((cx - w_s / 2, 880), t_sub, font=f_sub, fill=(0, 255, 180, 220))

    path = os.path.join(OUTPUT_DIR, "avatar_5_support_group_ru.png")
    img.save(path, "PNG")
    print(f"Saved: {path}")

if __name__ == "__main__":
    make_bot_avatar()
    make_ideas_avatar()
    make_chat_avatar()
    make_reviews_avatar()
    make_support_avatar()
    print("All 5 Russian avatars generated successfully!")
