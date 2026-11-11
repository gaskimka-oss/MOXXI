# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FONT_DIR = "C:/Windows/Fonts/"

FONTS = {
    "regular": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 16),
    "bold": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 17),
    "header": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 20),
    "small": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 13),
    "small_bold": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 13),
    "title": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 24),
    "mono": ImageFont.truetype(FONT_DIR + "consola.ttf", 14),
    "badge": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 12),
}

EMOJI_FONTS = {
    "regular": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 16),
    "bold": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 17),
    "header": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 20),
    "small": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 13),
    "small_bold": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 13),
    "title": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 24),
    "badge": ImageFont.truetype(FONT_DIR + "seguiemj.ttf", 12),
}

def render_mixed_text(draw, x, y, text, font_key, fill):
    font = FONTS.get(font_key, FONTS["regular"])
    emj_font = EMOJI_FONTS.get(font_key, EMOJI_FONTS["regular"])
    cur_x = x
    chunk = ""
    is_curr_emoji = None
    for char in text:
        code = ord(char)
        char_is_emoji = (code > 0x2190 and not (0x0400 <= code <= 0x052F)) and (
            code > 0x2500 or code in [0x2190, 0x2192, 0x2194, 0x2022, 0x2713, 0x2714, 0x2716, 0x2705]
        )
        if is_curr_emoji is None:
            is_curr_emoji = char_is_emoji
            chunk = char
        elif char_is_emoji == is_curr_emoji:
            chunk += char
        else:
            f = emj_font if is_curr_emoji else font
            draw.text((cur_x, y), chunk, font=f, fill=fill)
            cur_x += int(f.getlength(chunk))
            is_curr_emoji = char_is_emoji
            chunk = char
    if chunk:
        f = emj_font if is_curr_emoji else font
        draw.text((cur_x, y), chunk, font=f, fill=fill)
        cur_x += int(f.getlength(chunk))
    return cur_x - x

def get_mixed_text_width(text, font_key):
    font = FONTS.get(font_key, FONTS["regular"])
    emj_font = EMOJI_FONTS.get(font_key, EMOJI_FONTS["regular"])
    total_w = 0
    chunk = ""
    is_curr_emoji = None
    for char in text:
        code = ord(char)
        char_is_emoji = (code > 0x2190 and not (0x0400 <= code <= 0x052F)) and (
            code > 0x2500 or code in [0x2190, 0x2192, 0x2194, 0x2022, 0x2713, 0x2714, 0x2716, 0x2705]
        )
        if is_curr_emoji is None:
            is_curr_emoji = char_is_emoji
            chunk = char
        elif char_is_emoji == is_curr_emoji:
            chunk += char
        else:
            f = emj_font if is_curr_emoji else font
            total_w += int(f.getlength(chunk))
            is_curr_emoji = char_is_emoji
            chunk = char
    if chunk:
        f = emj_font if is_curr_emoji else font
        total_w += int(f.getlength(chunk))
    return total_w

def draw_beautiful_frame(scene_data: dict, progress: float, elapsed_sec: float, total_sec: float, scene_idx: int, total_scenes: int) -> Image.Image:
    # 1. Base Canvas (Deep Space Midnight)
    img = Image.new("RGB", (W, H), "#080c16")
    draw = ImageDraw.Draw(img)

    # Ambient Glow Spots (Subtle atmospheric cyber lighting)
    for r in range(160, 0, -8):
        alpha = int(14 * (r / 160))
        draw.ellipse([W - 300 - r, 80 - r, W - 300 + r, 80 + r], fill=(12 + alpha * 2, 8 + alpha, 35 + alpha * 3))
    for r in range(140, 0, -8):
        alpha = int(12 * (r / 140))
        draw.ellipse([200 - r, H - 120 - r, 200 + r, H - 120 + r], fill=(6 + alpha, 18 + alpha * 2, 30 + alpha * 2))

    # Subtle Cyber Dot Grid
    for gx in range(40, W - 40, 60):
        for gy in range(80, H - 50, 60):
            draw.point((gx, gy), fill="#141c2e")

    # 2. Header Bar (Glassmorphic Top Navigation)
    draw.rectangle([0, 0, W, 62], fill="#0e1424")
    draw.line([0, 62, W, 62], fill="#1e293b", width=1)
    draw.line([0, 63, W, 63], fill="#312e81", width=1)

    # Logo Icon
    draw.ellipse([24, 13, 58, 47], fill="#7c3aed", outline="#c084fc", width=2)
    draw.text((33, 16), "M", font=FONTS["title"], fill="#ffffff")
    
    # Project Title & Subtitle
    draw.text((70, 16), "MOXXI 3.0", font=FONTS["header"], fill="#f8fafc")
    draw.rounded_rectangle([186, 20, 300, 42], radius=4, fill="#1e1b4b", outline="#6366f1", width=1)
    draw.text((194, 23), "ЭКОСИСТЕМА", font=FONTS["badge"], fill="#a5b4fc")

    # 4 Platform Pills (Top Right) - strictly Russian Cyrillic "Макс"!
    platforms = [
        ("✈️ Telegram", "#0284c7"),
        ("🎮 Discord", "#6366f1"),
        ("🔷 ВКонтакте", "#2563eb"),
        ("⚡️ Макс", "#059669"),
    ]
    px = W - 530
    for p_name, p_border in platforms:
        draw.rounded_rectangle([px, 14, px + 120, 48], radius=8, fill="#131b2e", outline=p_border, width=1)
        render_mixed_text(draw, px + 10, 22, p_name, "small_bold", "#f1f5f9")
        px += 128

    # 3. Category Tag Above Left Column
    tag_text = scene_data.get("tag", "MOXXI 3.0")
    tag_w = get_mixed_text_width(tag_text, "badge") + 26
    draw.rounded_rectangle([32, 78, 32 + tag_w, 106], radius=6, fill="#2e1065", outline="#9333ea", width=1)
    render_mixed_text(draw, 45, 84, tag_text, "badge", "#e9d5ff")

    # 4. Right Column: High-End Feature Showcase Card
    cx, cy, cw, ch = W - 460, 78, 428, 574
    draw.rounded_rectangle([cx - 1, cy - 1, cx + cw + 1, cy + ch + 1], radius=16, fill="#0f172a", outline="#4338ca", width=2)
    draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=15, fill="#0b1120")

    # Showcase Card Header
    draw.rounded_rectangle([cx, cy, cx + cw, cy + 54], radius=15, fill="#1a1c3d")
    draw.rectangle([cx, cy + 30, cx + cw, cy + 54], fill="#1a1c3d")
    draw.line([cx, cy + 54, cx + cw, cy + 54], fill="#4f46e5", width=1)
    
    card_title = scene_data.get("card_title", "ВОЗМОЖНОСТИ MOXXI")
    render_mixed_text(draw, cx + 18, cy + 16, card_title, "bold", "#fbbf24")

    # Showcase Bullets
    bullets = scene_data.get("card_bullets", [])
    by = cy + 70
    for icon, text in bullets:
        card_item_h = 58
        draw.rounded_rectangle([cx + 14, by, cx + cw - 14, by + card_item_h], radius=10, fill="#131c31", outline="#1e293b", width=1)
        
        # Icon Circle
        draw.ellipse([cx + 24, by + 11, cx + 60, by + 47], fill="#1e293b", outline="#6366f1", width=1)
        render_mixed_text(draw, cx + 34, by + 15, icon, "regular", "#ffffff")

        # Bullet Text (Word Wrap)
        b_lines = []
        cur_line = ""
        for word in text.split(" "):
            test_l = cur_line + " " + word if cur_line else word
            if get_mixed_text_width(test_l, "small") > 310:
                b_lines.append(cur_line)
                cur_line = word
            else:
                cur_line = test_l
        if cur_line:
            b_lines.append(cur_line)

        ty = by + (18 if len(b_lines) == 1 else 10)
        for bl in b_lines[:2]:
            render_mixed_text(draw, cx + 70, ty, bl, "small", "#f8fafc")
            ty += 18

        by += card_item_h + 10

    # Showcase Card Footer
    draw.line([cx + 14, cy + ch - 60, cx + cw - 14, cy + ch - 60], fill="#1e293b", width=1)
    draw.ellipse([cx + 20, cy + ch - 42, cx + 30, cy + ch - 32], fill="#22c55e")
    render_mixed_text(draw, cx + 36, cy + ch - 44, "Серверы: Онлайн 100% • Отклик 12 мс", "small_bold", "#4ade80")
    render_mixed_text(draw, cx + 20, cy + ch - 22, f"Эпизод {scene_idx + 1} из {total_scenes} • MOXXI 3.0", "badge", "#94a3b8")

    # 5. Left Column: Chat Simulation Cards
    messages = scene_data.get("messages", [])
    if messages:
        y = 124
        for msg in messages:
            sender = msg.get("sender", "User")
            is_user = (sender in ["Игрок", "Сравнение"])
            text = msg.get("text", "")
            time_str = msg.get("time", "12:00")
            buttons = msg.get("buttons", [])

            lines = text.split("\n")
            bubble_w = 750
            bubble_h = len(lines) * 23 + 46 + (len(buttons) * 44 if buttons else 0)

            if is_user:
                bx = 32
                user_card_w = 460
                draw.rounded_rectangle([bx, y, bx + user_card_w, y + 46], radius=10, fill="#172554", outline="#2563eb", width=1)
                
                # User Avatar
                draw.ellipse([bx + 10, y + 8, bx + 38, y + 36], fill="#1d4ed8")
                render_mixed_text(draw, bx + 17, y + 10, "👤", "small", "#ffffff")
                
                # Text
                render_mixed_text(draw, bx + 48, y + 12, f"{sender}: {text}", "bold", "#93c5fd")
                render_mixed_text(draw, bx + user_card_w - 60, y + 14, f"{time_str} ✓✓", "small", "#60a5fa")
                y += 58
            else:
                bx = 32
                draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=14, fill="#0e1626", outline="#334155", width=1)
                
                # Bot Header
                draw.ellipse([bx + 14, y + 10, bx + 42, y + 38], fill="#7c3aed", outline="#a855f7", width=1)
                draw.text((bx + 20, y + 11), "M", font=FONTS["bold"], fill="#ffffff")
                render_mixed_text(draw, bx + 52, y + 13, sender, "bold", "#c084fc")
                
                # Verification Pill Badge
                draw.rounded_rectangle([bx + 120, y + 13, bx + 265, y + 33], radius=4, fill="#1e1b4b", outline="#6366f1", width=1)
                render_mixed_text(draw, bx + 128, y + 14, "✓ БОТ ВЕРИФИЦИРОВАН", "badge", "#a5b4fc")

                cy_m = y + 46
                for l in lines:
                    color = "#f8fafc"
                    if "⛔️" in l or "🔴" in l or "❌" in l:
                        color = "#f87171"
                    elif "✅" in l or "🟢" in l or "🎉" in l or "ПОБЕДА" in l:
                        color = "#4ade80"
                    elif "💡" in l or "💰" in l or "🎯" in l or "🎁" in l or "👑" in l or "💎" in l:
                        color = "#fbbf24"
                    elif "•" in l or "👉" in l or "1." in l or "2." in l or "3." in l:
                        color = "#e2e8f0"
                    elif "⚡️" in l or "🌐" in l:
                        color = "#38bdf8"
                    render_mixed_text(draw, bx + 18, cy_m, l, "regular", color)
                    cy_m += 23

                if buttons:
                    cy_m += 6
                    btn_w = (bubble_w - 36 - (len(buttons) - 1) * 12) // len(buttons)
                    for bi, btn in enumerate(buttons):
                        btn_x = bx + 18 + bi * (btn_w + 12)
                        draw.rounded_rectangle([btn_x, cy_m, btn_x + btn_w, cy_m + 34], radius=8, fill="#1e1b4b", outline="#6366f1", width=1)
                        t_len = get_mixed_text_width(btn, "small_bold")
                        tx_btn = btn_x + max(4, int((btn_w - t_len) / 2))
                        render_mixed_text(draw, tx_btn, cy_m + 8, btn, "small_bold", "#93c5fd")

                y += bubble_h + 14

    # 6. Bottom Bar (Modern Player Timeline & Ticker)
    draw.rectangle([0, H - 42, W, H], fill="#070b14")
    draw.line([0, H - 42, W, H - 42], fill="#1e293b", width=1)

    # Scrubber Bar
    total_prog = min(1.0, max(0.0, elapsed_sec / max(1.0, total_sec)))
    prog_w = int(W * total_prog)
    draw.rectangle([0, H - 42, W, H - 39], fill="#1e293b")
    draw.rectangle([0, H - 42, prog_w, H - 39], fill="#38bdf8")
    if prog_w > 6:
        draw.ellipse([prog_w - 5, H - 44, prog_w + 5, H - 37], fill="#ffffff", outline="#38bdf8", width=1)

    # Time Counter
    cur_m, cur_s = divmod(int(elapsed_sec), 60)
    tot_m, tot_s = divmod(int(total_sec), 60)
    time_display = f"⏱ {cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}"
    render_mixed_text(draw, 24, H - 28, time_display, "small_bold", "#94a3b8")

    # Scrolling Banner / Promo Code
    cta_text = "🎁 Промокод: ОБНОВА3.0 (+2.500.000 монет) | 💬 Чат: @moxxi_chat | 🎮 Discord: discord.gg/7hDq4R2q | 4 Платформы: TG • DS • VK • Макс"
    render_mixed_text(draw, W - get_mixed_text_width(cta_text, "badge") - 24, H - 26, cta_text, "badge", "#38bdf8")

    return img

if __name__ == "__main__":
    sample_scene = {
        "id": "scene01_launch_4platforms",
        "tag": "🔥 ГЛОБАЛЬНЫЙ РЕЛИЗ • 4 ПЛАТФОРМЫ",
        "card_title": "MOXXI 3.0: МЫ ВЕЗДЕ!",
        "card_bullets": [
            ("✈️", "Telegram: Флагманский бот и неоновый Mini App"),
            ("🎮", "Discord: Игровой бот и 24/7 хаб поддержки"),
            ("🔷", "ВКонтакте: Полная экосистема для бесед"),
            ("⚡️", "Макс: Скоростной кроссплатформенный мост")
        ],
        "messages": [
            {
                "sender": "Игрок",
                "text": "старт",
                "time": "12:00"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "✨ ДОБРО ПОЖАЛОВАТЬ В ЭКОСИСТЕМУ MOXXI 3.0!\n\n"
                    "👑 Профиль: @cyber_hero (Ранг: Легенда)\n"
                    "💰 Баланс: 25,000,000 монет | VIP Platinum\n"
                    "🌐 Платформы: Telegram • Discord • VK • Макс\n"
                    "🏢 Предприятия: 40/40 под контролем\n\n"
                    "Выберите раздел игры:"
                ),
                "buttons": ["🎰 Казино 3.0", "🐉 Рейды на боссов", "🏢 Мои бизнесы"],
                "time": "12:00"
            }
        ]
    }
    img = draw_beautiful_frame(sample_scene, 0.25, 45.0, 270.0, 0, 10)
    img.save("sample_preview_scene1.png")
    print("Saved sample_preview_scene1.png successfully!")
