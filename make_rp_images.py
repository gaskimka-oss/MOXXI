import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from h_rp import ACTIONS

def create_rp_images():
    out_dir = Path("rp_images")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    W, H = 720, 400
    
    # Пытаемся найти системные шрифты
    font_title = None
    font_subtitle = None
    font_badge = None
    
    font_paths = [
        "C:\\Windows\\Fonts\\segoeuib.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    chosen_path = None
    for p in font_paths:
        if os.path.exists(p):
            chosen_path = p
            break
            
    if chosen_path:
        try:
            font_title = ImageFont.truetype(chosen_path, 42)
            font_subtitle = ImageFont.truetype(chosen_path, 26)
            font_badge = ImageFont.truetype(chosen_path, 18)
        except Exception:
            pass

    palettes = [
        ((18, 12, 38), (85, 25, 120), (255, 60, 150)),   # Кибер-маджента
        ((10, 20, 45), (20, 65, 140), (0, 215, 255)),    # Неон-циан
        ((15, 30, 25), (25, 95, 70), (45, 245, 140)),    # Изумрудный кибер
        ((35, 15, 15), (120, 35, 35), (255, 110, 45)),   # Пламенный
        ((25, 15, 40), (70, 30, 110), (190, 80, 255)),   # Неоновый аметист
    ]

    for idx, (action, (emoji, verb)) in enumerate(ACTIONS.items(), 1):
        filename = out_dir / f"rp_{idx:02d}.jpg"
        
        bg_dark, bg_mid, accent = palettes[(idx - 1) % len(palettes)]
        
        im = Image.new("RGB", (W, H), bg_dark)
        draw = ImageDraw.Draw(im)
        
        # Градиентный фон
        for y in range(H):
            ratio = y / H
            r = int(bg_dark[0] * (1 - ratio) + bg_mid[0] * ratio)
            g = int(bg_dark[1] * (1 - ratio) + bg_mid[1] * ratio)
            b = int(bg_dark[2] * (1 - ratio) + bg_mid[2] * ratio)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
            
        # Неоновые светящиеся круги на фоне
        for rad, alpha in [(160, 25), (110, 40), (60, 70)]:
            cx, cy = W // 2, H // 2 - 20
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=accent, width=2)

        # Рамка
        pad = 20
        draw.rounded_rectangle([pad, pad, W - pad, H - pad], radius=18, outline=accent, width=3)
        draw.rounded_rectangle([pad + 5, pad + 5, W - pad - 5, H - pad - 5], radius=14, outline=(255, 255, 255), width=1)

        # Верхняя плашка
        badge_text = "✨ MOXXI ROLEPLAY · ИНТЕРАКТИВ ✨"
        if font_badge:
            bbox = font_badge.getbbox(badge_text)
            bw = bbox[2] - bbox[0]
            draw.text(((W - bw) // 2, pad + 15), badge_text, fill=(220, 230, 255), font=font_badge)

        # Центр: Название действия
        title_text = f"{emoji} {action.upper()}"
        if font_title:
            bbox = font_title.getbbox(title_text)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, H // 2 - 40), title_text, fill=(255, 255, 255), font=font_title)
        else:
            draw.text((W // 2 - 100, H // 2 - 30), title_text, fill=(255, 255, 255))

        # Подзаголовок: глагол
        desc_text = f"«{verb.capitalize()}...»"
        if font_subtitle:
            bbox = font_subtitle.getbbox(desc_text)
            dw = bbox[2] - bbox[0]
            draw.text(((W - dw) // 2, H // 2 + 35), desc_text, fill=accent, font=font_subtitle)
        else:
            draw.text((W // 2 - 80, H // 2 + 30), desc_text, fill=accent)

        # Нижний футер
        footer_text = "💎 MOXXI 2027 · ВСЕГДА АКТИВНО"
        if font_badge:
            bbox = font_badge.getbbox(footer_text)
            fw = bbox[2] - bbox[0]
            draw.text(((W - fw) // 2, H - pad - 35), footer_text, fill=(160, 175, 210), font=font_badge)

        im.save(filename, "JPEG", quality=90)

    print(f"Successfully generated {len(ACTIONS)} RP images in rp_images/")

if __name__ == "__main__":
    create_rp_images()
