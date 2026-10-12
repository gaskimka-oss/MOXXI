import os
import re
import sys
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SCENES = [
    {
        "id": "scene1",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene1_intro_1791698402645.jpg",
        "audio": "scene1.mp3",
        "tag": "MOXXI 2.1 • ВСТУПЛЕНИЕ",
        "title": "ДОБРО ПОЖАЛОВАТЬ В МИР MOXXI",
        "desc": "Твой персональный мир азарта, власти и развлечений в Telegram",
        "pan": "zoom_in"
    },
    {
        "id": "scene2",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene2_casino_1791698428497.jpg",
        "audio": "scene2.mp3",
        "tag": "КАЗИНО & ИГРОВАЯ ЗОНА",
        "title": "НЕОНОВОЕ КАЗИНО • СЛОТЫ • ДЖЕКПОТ",
        "desc": "Кнопки реплея, блэкджек, рулетка, кубики и общий банк чата",
        "pan": "pan_right"
    },
    {
        "id": "scene3",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene3_business_1791698441757.jpg",
        "audio": "scene3.mp3",
        "tag": "ЭКОНОМИЧЕСКАЯ ИМПЕРИЯ",
        "title": "30 БИЗНЕСОВ ДО 100 LVL",
        "desc": "От шаурмичной до космостанции • Реальный пассивный доход в минуту",
        "pan": "zoom_out"
    },
    {
        "id": "scene4",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene4_boss_1791698456705.jpg",
        "audio": "scene4.mp3",
        "tag": "RPG & БОЕВЫЕ РЕЖИМЫ",
        "title": "РЕЙДЫ НА БОССОВ • КЛАНЫ • PvP ДУЭЛИ",
        "desc": "Подземелья, крафт снаряжения, клановая база, дуэли и рыбалка",
        "pan": "zoom_in"
    },
    {
        "id": "scene5",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene5_social_1791698471518.jpg",
        "audio": "scene5.mp3",
        "tag": "СОЦИУМ & ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ",
        "title": "ТАРО • ПАРА ДНЯ • МОКСИ GEMINI AI",
        "desc": "Гороскопы, таймеры, радио-вайб и живые диалоги с нейросетью",
        "pan": "zoom_in"
    }
]

def get_audio_duration(audio_file):
    cmd = [FFMPEG_EXE, "-i", audio_file]
    p = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", p.stderr)
    if m:
        h, mn, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return h * 3600 + mn * 60 + s
    return 14.0

def create_ui_overlay(width, height, tag, title, desc, progress, scene_num, total_scenes):
    """Creates a transparent RGBA PIL Image overlay with subtitles, badges, and progress bar."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    font_reg_path = r"C:\Windows\Fonts\arial.ttf"

    font_tag = ImageFont.truetype(font_bold_path, 18)
    font_title = ImageFont.truetype(font_bold_path, 34)
    font_desc = ImageFont.truetype(font_reg_path, 22)
    font_bot = ImageFont.truetype(font_bold_path, 16)

    # 1. Top Bar: Badge
    badge_x, badge_y = 40, 36
    draw.rounded_rectangle([badge_x, badge_y, badge_x + 320, badge_y + 36], radius=8, fill=(15, 10, 30, 200), outline=(255, 45, 150, 180), width=1)
    # Glowing dot
    draw.ellipse([badge_x + 14, badge_y + 13, badge_x + 24, badge_y + 23], fill=(0, 255, 200, 255))
    draw.text((badge_x + 34, badge_y + 8), tag, font=font_tag, fill=(255, 255, 255, 255))

    # Top Right Watermark / Bot info
    wm_text = f"@moxxichat_bot  [{scene_num}/{total_scenes}]"
    draw.rounded_rectangle([width - 240, badge_y, width - 40, badge_y + 36], radius=8, fill=(15, 10, 30, 180), outline=(0, 220, 255, 140), width=1)
    draw.text((width - 225, badge_y + 8), wm_text, font=font_bot, fill=(0, 230, 255, 240))

    # 2. Bottom Glassmorphic Banner
    banner_h = 150
    banner_top = height - banner_h
    # Dark gradient-like background
    draw.rectangle([0, banner_top, width, height], fill=(10, 8, 22, 220))
    # Neon accent top border line
    draw.line([(0, banner_top), (width, banner_top)], fill=(255, 0, 128, 200), width=2)

    # Title shadow and text
    tx, ty = 45, banner_top + 24
    # Shadow
    draw.text((tx + 2, ty + 2), title, font=font_title, fill=(0, 0, 0, 230))
    # Main text (Cyan neon / gold glow)
    draw.text((tx, ty), title, font=font_title, fill=(255, 220, 90, 255))

    # Description subtitle
    dx, dy = 45, banner_top + 76
    draw.text((dx + 1, dy + 1), desc, font=font_desc, fill=(0, 0, 0, 200))
    draw.text((dx, dy), desc, font=font_desc, fill=(225, 235, 255, 240))

    # 3. Dynamic Progress Bar at very bottom
    pb_y = height - 6
    draw.rectangle([0, pb_y, width, height], fill=(20, 20, 30, 150))
    bar_width = int(width * progress)
    if bar_width > 0:
        draw.rectangle([0, pb_y, bar_width, height], fill=(0, 240, 255, 255))

    return overlay

def render_scene(scene_idx, scene, width=1280, height=720, fps=30):
    audio_dur = get_audio_duration(scene["audio"])
    total_duration = audio_dur + 0.4
    total_frames = int(total_duration * fps)

    img_bgr = cv2.imread(scene["image"])
    if img_bgr is None:
        raise ValueError(f"Cannot load image: {scene['image']}")
    img_h, img_w = img_bgr.shape[:2]

    # Pre-render base text overlay image without progress bar
    # and we can update the progress bar per frame
    tag = scene["tag"]
    title = scene["title"]
    desc = scene["desc"]

    out_silent = f"temp_silent_{scene['id']}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(out_silent, fourcc, fps, (width, height))

    pan_type = scene.get("pan", "zoom_in")

    for f in range(total_frames):
        t = f / float(total_frames)

        # Camera motion math
        if pan_type == "zoom_in":
            zoom = 1.0 + 0.08 * t
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            x1 = (img_w - crop_w) // 2
            y1 = (img_h - crop_h) // 2
        elif pan_type == "zoom_out":
            zoom = 1.08 - 0.08 * t
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            x1 = (img_w - crop_w) // 2
            y1 = (img_h - crop_h) // 2
        elif pan_type == "pan_right":
            zoom = 1.06
            crop_w = int(img_w / zoom)
            crop_h = int(img_h / zoom)
            max_drift = img_w - crop_w
            x1 = int(max_drift * 0.2 + max_drift * 0.6 * t)
            y1 = (img_h - crop_h) // 2
        else:
            zoom = 1.0
            crop_w, crop_h = img_w, img_h
            x1, y1 = 0, 0

        x1 = max(0, min(img_w - crop_w, x1))
        y1 = max(0, min(img_h - crop_h, y1))

        cropped = img_bgr[y1:y1+crop_h, x1:x1+crop_w]
        frame_bgr = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)

        # Convert to RGB PIL for compositing overlay
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_frame = Image.fromarray(frame_rgb).convert("RGBA")

        # Create overlay with progress
        overlay = create_ui_overlay(width, height, tag, title, desc, t, scene_idx + 1, len(SCENES))
        pil_frame = Image.alpha_composite(pil_frame, overlay)

        # Convert back to BGR numpy for OpenCV
        final_bgr = cv2.cvtColor(np.array(pil_frame.convert("RGB")), cv2.COLOR_RGB2BGR)
        writer.write(final_bgr)

    writer.release()

    # Mux audio with silent video
    out_scene = f"scene_{scene['id']}.mp4"
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", out_silent,
        "-i", scene["audio"],
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_scene
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(out_silent):
        os.remove(out_silent)
    print(f"Scene {scene['id']} complete -> {out_scene}")
    return out_scene

def concat_all(scene_files, final_output):
    concat_list = "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")

    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        final_output
    ]
    subprocess.run(cmd, check=True)
    if os.path.exists(concat_list):
        os.remove(concat_list)
    print(f"Final promo video rendered -> {final_output}")

def main():
    print("=== STARTING MOXXI PROMO VIDEO RENDERING ===")
    scene_files = []
    for idx, sc in enumerate(SCENES):
        print(f"Rendering Scene {idx+1}/{len(SCENES)}: {sc['title']}...")
        sf = render_scene(idx, sc)
        scene_files.append(sf)

    final_video = "moxxi_promo_video.mp4"
    print("Concatenating scenes into final presentation...")
    concat_all(scene_files, final_video)
    print(f"All done! Video saved to {final_video}")

if __name__ == "__main__":
    main()
