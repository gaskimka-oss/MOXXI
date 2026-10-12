import os
import subprocess
import imageio_ffmpeg
import cv2
import numpy as np

# Path to ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SCENES = [
    {
        "id": "scene1",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene1_intro_1791698402645.jpg",
        "audio": "scene1.mp3",
        "title": "MOXXI 2.1",
        "sub": "Твой персональный мир азарта, власти и развлечений"
    },
    {
        "id": "scene2",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene2_casino_1791698428497.jpg",
        "audio": "scene2.mp3",
        "title": "НЕОНОВОЕ КАЗИНО & СЛОТЫ",
        "sub": "Слоты 777 • Блэкджек • Рулетка • Общий Джекпот"
    },
    {
        "id": "scene3",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene3_business_1791698441757.jpg",
        "audio": "scene3.mp3",
        "title": "30 БИЗНЕСОВ ДО 100 LVL",
        "sub": "Построй финансовую империю • Пассивный доход"
    },
    {
        "id": "scene4",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene4_boss_1791698456705.jpg",
        "audio": "scene4.mp3",
        "title": "РЕЙДЫ НА БОССОВ & PvP",
        "sub": "Титанические боссы • Дуэли на монеты • Крафт"
    },
    {
        "id": "scene5",
        "image": r"C:\Users\eiema\.gemini\antigravity\brain\b2d637ac-cb69-458c-9dcc-6512df9c5df9\moxxi_scene5_social_1791698471518.jpg",
        "audio": "scene5.mp3",
        "title": "ТАРО, ПАРА ДНЯ & GEMINI AI",
        "sub": "Живое общение с Мокси • Атмосфера и уют"
    }
]

def get_audio_duration(audio_file):
    cmd = [
        FFMPEG_EXE, "-i", audio_file
    ]
    p = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    # Search for Duration: 00:00:11.23
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", p.stderr)
    if m:
        hours = float(m.group(1))
        mins = float(m.group(2))
        secs = float(m.group(3))
        return hours * 3600 + mins * 60 + secs
    return 10.0

def make_scene_video(scene, output_video, width=1280, height=720, fps=30):
    audio_dur = get_audio_duration(scene["audio"])
    total_duration = audio_dur + 0.5  # slight buffer
    total_frames = int(total_duration * fps)

    img = cv2.imread(scene["image"])
    if img is None:
        raise ValueError(f"Cannot read {scene['image']}")

    # Convert BGR to RGB? OpenCV VideoWriter uses BGR
    img_h, img_w = img.shape[:2]

    # Create temporary silent video with Ken Burns effect (smooth zoom / pan)
    temp_silent = f"temp_{scene['id']}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_silent, fourcc, fps, (width, height))

    # Zoom from 1.0 to 1.12 over the scene
    for f in range(total_frames):
        t = f / float(total_frames)
        zoom = 1.0 + 0.10 * t
        
        # Crop window based on zoom
        crop_w = int(img_w / zoom)
        crop_h = int(img_h / zoom)

        # Center pan with slight horizontal drifting
        drift = int((img_w - crop_w) * 0.1 * np.sin(t * np.pi))
        x1 = max(0, min(img_w - crop_w, (img_w - crop_w) // 2 + drift))
        y1 = max(0, min(img_h - crop_h, (img_h - crop_h) // 2))
        
        cropped = img[y1:y1+crop_h, x1:x1+crop_w]
        frame = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LINEAR)

        # Overlay bottom banner gradient for readable cinematic subtitles
        banner_h = 160
        overlay = frame[-banner_h:, :].copy()
        cv2.rectangle(overlay, (0, 0), (width, banner_h), (10, 5, 20), -1)
        # alpha blend
        alpha = 0.65
        cv2.addWeighted(overlay, alpha, frame[-banner_h:, :], 1 - alpha, 0, frame[-banner_h:, :])

        # Add Title and Subtitle text using Hershey or simple text
        # Glow / shadow for title
        title_text = scene["title"]
        sub_text = scene["sub"]

        # Title shadow
        cv2.putText(frame, title_text, (52, height - 90), cv2.FONT_HERSHEY_DUPLEX, 1.25, (0, 0, 0), 4, cv2.LINE_AA)
        # Title text (Neon cyan/gold)
        cv2.putText(frame, title_text, (50, height - 92), cv2.FONT_HERSHEY_DUPLEX, 1.25, (0, 240, 255), 2, cv2.LINE_AA)

        # Subtitle shadow
        # Note: Since cv2.putText does not support Russian Cyrillic cleanly without FreeType,
        # we will use PIL to render beautiful Cyrillic font onto the frame!
        writer.write(frame)

    writer.release()

    # Now mux temp_silent + scene["audio"] using ffmpeg
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
    print(f"Scene {scene['id']} built successfully: {output_video}")

if __name__ == "__main__":
    print("Testing audio durations:")
    for sc in SCENES:
        if os.path.exists(sc["audio"]):
            d = get_audio_duration(sc["audio"])
            print(f"{sc['id']}: {d:.2f}s")
