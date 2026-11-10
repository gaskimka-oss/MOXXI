# -*- coding: utf-8 -*-
"""
MOXXI 3.0 ECOSYSTEM - 5-MINUTE MASTER SHOWCASE VIDEO GENERATOR
For TikTok & YouTube

Features highlighted:
1. Intro: The MOXXI 3.0 Global Ecosystem
2. Multiplatform: Telegram (Bot + Mini App), Discord (Staff Desk), VK, MAX Messenger
3. Iris vs MOXXI: The In-Depth Breakdown (Why Iris is dead)
4. Instant 1-Click Setup: !авточат & !автоштаб
5. Omnichannel 24/7 Support Desk & Ticket Bridge (TG ⇄ DS ⇄ VK ⇄ MAX)
6. Gemini AI Engine: Voice & Circle STT, Copilot, Smart Announcements
7. Gaming & Economy: Casino 3.0 (Roulette x36, Slots, Dice), 40 Businesses, Boss Raids
8. Administration & Security: Anti-Leak, Duty Shifts, Swarns
9. Roadmap & The Future: Web3, Cross-platform Tournaments, Global Expansion
10. Outro: Call to Action, Community Links, Promo Code ОБНОВА3.0

Engine: Pillow RGB24 + FFmpeg Direct Pipe + EdgeTTS (ru-RU-SvetlanaNeural)
Resolution: 1280x720 (720p HD)
"""
import os
import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8')
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
    "header": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 21),
    "small": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 14),
    "small_bold": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 14),
    "input": ImageFont.truetype(FONT_DIR + "segoeui.ttf", 17),
    "title": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 25),
    "mono": ImageFont.truetype(FONT_DIR + "consola.ttf", 15),
    "badge": ImageFont.truetype(FONT_DIR + "segoeuib.ttf", 13),
}

SCENES = [
    {
        "id": "scene01_intro_revolution",
        "tag": "ГЛОБАЛЬНЫЙ РЕЛИЗ • ЭКОСИСТЕМА 3.0",
        "card_title": "ЭРА MOXXI 3.0 REVOLUTION",
        "card_bullets": [
            ("🌐", "Единая экосистема для всех платформ"),
            ("🧠", "Нейросетевой ИИ-копилот Google Gemini"),
            ("🛡", "Железная автомодерация и защита от сливов"),
            ("🎮", "Казино 3.0, 40 бизнесов и мировые боссы")
        ],
        "voice": (
            "Добро пожаловать в новую эру управления и развлечений! Представляем глобальное обновление MOXXI 3.0. "
            "Это больше не просто бот для бесед — это масштабная экосистема нового поколения, объединяющая искусственный "
            "интеллект, захватывающую экономику, клановые войны и полную безопасность. Сегодня мы покажем всё, что "
            "появилось в проекте, докажем, почему Ирис безнадёжно устарел, и раскроем наши грандиозные планы на будущее!"
        ),
        "messages": [
            {
                "sender": "Создатель",
                "text": "старт",
                "time": "12:00"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🚀 Добро пожаловать во вселенную MOXXI 3.0!\n\n"
                    "💎 Профиль: @founder (Ранг 10 — Владелец)\n"
                    "💰 Баланс: 15,000,000 монет | VIP Diamond\n"
                    "👑 Клан: 『LEGION』 • Рейтинг: Топ 1\n"
                    "🏢 Предприятия: 40/40 под контролем\n\n"
                    "Выберите раздел управления:"
                ),
                "buttons": ["🎮 Игры & Казино", "💼 Империя бизнесов", "🛡 Штаб & Защита"],
                "time": "12:00"
            }
        ]
    },
    {
        "id": "scene02_all_platforms",
        "tag": "МУЛЬТИПЛАТФОРМЕННОСТЬ • ВСЕ ПРИЛОЖЕНИЯ",
        "card_title": "МЫ ВЕЗДЕ: TG, DISCORD, VK, MAX",
        "card_bullets": [
            ("✈️", "Telegram: Чат-бот + интерактивный Mini App"),
            ("🎮", "Discord: Саппорт-деск & авто-очередь жалоб"),
            ("🔷", "ВКонтакте: Полный перенос команд и базы"),
            ("🟢", "MAX Messenger: Кроссплатформенный мост")
        ],
        "voice": (
            "Главный прорыв MOXXI 3.0 — полная мультиплатформенность! Теперь бот доступен во всех ваших любимых сервисах. "
            "В Телеграме работает флагманский бот с интерактивным Web App приложением. В Дискорде запущен официальный "
            "саппорт-бот с автоматической очередью жалоб и синхронизацией ролей. Во ВКонтакте и новом мессенджере MAX наши "
            "боты мгновенно обрабатывают запросы аудитории. Ваш игровой прогресс, баланс и статус защищены и "
            "синхронизированы в единой базе данных!"
        ),
        "messages": [
            {
                "sender": "MOXXI Mini App",
                "text": (
                    "📱 TELEGRAM MINI APP & DISCORD CONNECTED!\n\n"
                    "• Web App: Живой неоновый интерфейс профиля\n"
                    "• Discord Guild: MOXXI Support (#🚨・очередь-жалоб)\n"
                    "• VK Community: MOXXI Bot • Полный коннект\n"
                    "• Мессенджер MAX: Авто-синхронизация тикетов\n\n"
                    "Единый профиль игрока на всех 4 платформах!"
                ),
                "buttons": ["🌐 Открыть Web App", "🚨 Discord Стафф-деск"],
                "time": "12:01"
            }
        ]
    },
    {
        "id": "scene03_iris_vs_moxxi",
        "tag": "БИТВА ТЕХНОЛОГИЙ • MOXXI VS IRIS",
        "card_title": "ПОЧЕМУ MOXXI РАЗРЫВАЕТ ИРИС?",
        "card_bullets": [
            ("❌", "Ирис: Устаревший текст 2018 года без кнопок"),
            ("✅", "MOXXI: Неоновый UI, Mini App, кнопки в 1 клик"),
            ("❌", "Ирис: Сливы чата обиженными модераторами"),
            ("✅", "MOXXI: Анти-слив, смены /duty и сварны")
        ],
        "voice": (
            "Почему тысячи бесед массово переходят с Ириса на MOXXI? Посмотрите на факты! Ирис застрял в две тысячи "
            "восемнадцатом году: серые простыни монохромного текста, медленный отклик и нулевое развитие. В MOXXI — "
            "современный дизайн, инлайн-кнопки, удобный веб-интерфейс, распознавание голосовых сообщений и кружочков, "
            "сорок видов бизнеса и защита от сливов. Пока Ирис годами стоит на месте, MOXXI внедряет технологии будущего "
            "каждую неделю!"
        ),
        "messages": [
            {
                "sender": "Аналитика",
                "text": (
                    "📊 СРАВНИТЕЛЬНЫЙ АНАЛИЗ:\n\n"
                    "🔴 ИРИС БОТ:\n"
                    "• Монохромный текст без инлайн-кнопок\n"
                    "• 0% Искусственного интеллекта\n"
                    "• Нет Discord, VK и Web App связки\n\n"
                    "🟢 MOXXI 3.0:\n"
                    "• Полноценный Telegram Web App\n"
                    "• Нейросеть Gemini + расшифровка ГС и кружков\n"
                    "• Омнисерверная поддержка и защита бесед"
                ),
                "buttons": ["🏆 Перейти на MOXXI 3.0"],
                "time": "12:02"
            }
        ]
    },
    {
        "id": "scene04_autochat_autohq",
        "tag": "АВТОМАТИЗАЦИЯ В 1 КЛИК • !АВТОЧАТ",
        "card_title": "АВТО-РАЗВЁРТЫВАНИЕ ЧАТА ЗА 5 СЕКУНД",
        "card_bullets": [
            ("⚡️", "Развёртывание 7 форумов-топиков за 3 сек"),
            ("📜", "Автоматический регламент и правила чата"),
            ("🎁", "Промокод ОБНОВА3.0 на 2,500,000 монет"),
            ("🛡", "Готовая защита: антимат, антиспам, антирейд")
        ],
        "voice": (
            "Устали часами вручную создавать темы и настраивать права? В MOXXI появилась революционная команда "
            "«восклицательный знак авточат»! Всего один клик — и бот моментально превращает вашу группу в образцовый форум: "
            "создаёт топики для общения, казино, рейдов, правил и команд, публикует регламент и дарит участникам секретный "
            "промокод на два с половиной миллиона монет! А команда «автоштаб» строит закрытый бункер для вашей "
            "администрации с ИИ-копилотом."
        ),
        "messages": [
            {
                "sender": "Создатель",
                "text": "!авточат",
                "time": "12:03"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "✨ СУПЕРГРУППА УСПЕШНО НАСТРОЕНА «ПОД КЛЮЧ»!\n\n"
                    "Создано 7 официальных топиков:\n"
                    "• 📜 #правила-и-новости (закреплён регламент)\n"
                    "• 💬 #общение-и-флуд (главный зал общения)\n"
                    "• 🎰 #казино-и-игры (зона азарта)\n"
                    "• ⚔️ #рейды-и-боссы (арена боссов)\n"
                    "• 📖 #команды-и-бот (справочник команд)\n\n"
                    "🎁 Промокод «ОБНОВА3.0» активирован для всех!"
                ),
                "buttons": ["📜 Правила беседы", "🎁 Забрать 2.500.000"],
                "time": "12:03"
            }
        ]
    },
    {
        "id": "scene05_omnichannel_support",
        "tag": "ОМНИКАНАЛЬНЫЙ СТАФФ-ХАБ 24/7",
        "card_title": "ЕДИНЫЙ ТИКЕТ-МОСТ 24/7",
        "card_bullets": [
            ("🔗", "Мост тикетов Telegram ⇄ Discord ⇄ VK ⇄ MAX"),
            ("🔒", "Защита от дублей: статус «Занят модератором»"),
            ("📢", "Авто-оповещения каждые 3 часа о поддержке"),
            ("💡", "Прямой сбор идей и багрепортов комьюнити")
        ],
        "voice": (
            "Поддержка пользователей теперь работает как швейцарские часы. Любое сообщение с командами «поддержка», «баг» "
            "или «идея» из Телеграма, ВКонтакте или мессенджера MAX моментально пересылается в штаб стаффа и специальный "
            "канал Дискорда. Как только модератор берёт тикет в работу, статус обновляется везде, исключая дубликаты. "
            "А каждые три часа бот заботливо напоминает игрокам в беседах, куда обращаться при любых вопросах!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "баг не пришли монеты с бонуса",
                "time": "12:04"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎫 ТИКЕТ ПОДДЕРЖКИ #1042 УСПЕШНО СОЗДАН!\n\n"
                    "Категория: 🛠 Баг / Ошибка\n"
                    "Статус: 🟡 Ожидает модератора\n\n"
                    "⚡️ Ваше обращение отправлено в Discord Штаб и TG Staff.\n"
                    "Модератор ответит вам в течение нескольких минут!"
                ),
                "buttons": ["👤 Занять тикет", "✅ Закрыть тикет"],
                "time": "12:04"
            }
        ]
    },
    {
        "id": "scene06_ai_voice_stt",
        "tag": "НЕЙРОСЕТИ • GOOGLE GEMINI AI",
        "card_title": "ИИ-КОПИЛОТ И РАСПОЗНАВАНИЕ РЕЧИ",
        "card_bullets": [
            ("🎙", "Мгновенный перевод ГС и видео-кружков в текст"),
            ("🤖", "Живой ИИ-собеседник по команде «ии»"),
            ("💡", "ИИ-копилот для модераторов и тикетов"),
            ("📝", "Автогенерация красивых постов и анонсов")
        ],
        "voice": (
            "Искусственный интеллект — гордость MOXXI! Интегрированный движок Google Gemini превращает бота в живого "
            "эрудированного собеседника. Не любите слушать длинные голосовые или смотреть видеосообщения? MOXXI мгновенно "
            "переводит любые войсы и видео-кружки в удобный читаемый текст. А для модераторов работает умный ИИ-копилот, "
            "который подсказывает правильное решение по правилам чата за полсекунды!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "🎤 [Голосовое сообщение 0:14]",
                "time": "12:05"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎙 РАСПОЗНАННЫЙ ТЕКСТ ГОЛОСОВОГО:\n\n"
                    "«Ребята, собираемся сегодня в девять вечера\n"
                    "на штурм мирового дракона в теме боссов!»\n\n"
                    "⚡️ Переведено с помощью MOXXI Neural STT"
                ),
                "buttons": ["🤖 Спросить ИИ", "⚔️ Идти на рейд"],
                "time": "12:05"
            }
        ]
    },
    {
        "id": "scene07_economy_casino_rpg",
        "tag": "ИГРЫ & ЭКОНОМИКА 3.0",
        "card_title": "КАЗИНО 3.0, РЕЙДЫ И 40 БИЗНЕСОВ",
        "card_bullets": [
            ("🎲", "Европейская рулетка x36, слоты, кости, 21"),
            ("🏢", "40 предприятий и пассивный доход"),
            ("🐉", "Мировые боссы с фазами ярости и данжи"),
            ("⚔️", "Войны синдикатов за районы мегаполиса")
        ],
        "voice": (
            "Игровая вселенная MOXXI захватывает с первых минут! Настоящее европейское казино с рулеткой на тридцать шесть "
            "чисел, костями, слотами и блэкджеком прямо на кнопках. Развивайте свою финансовую империю: покупайте до "
            "сорока предприятий, открывайте банковские депозиты под процент и торгуйте на бирже. А для любителей битв — "
            "эпические рейд-боссы, подземелья, крафт снаряжения и захват городских районов вашим синдикатом!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "рулетка 100000 красное",
                "time": "12:06"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА MOXXI!\n\n"
                    "🎯 Выпало: 🔴 14 КРАСНОЕ!\n"
                    "🎉 ПОБЕДА! Вы угадали цвет!\n\n"
                    "💰 Выигрыш: +200,000 монет (x2.0)\n"
                    "💵 Текущий баланс: 1,450,000 монет"
                ),
                "buttons": ["🎰 Крутить ещё", "2x Удвоить", "🏢 Мои бизнесы"],
                "time": "12:06"
            }
        ]
    },
    {
        "id": "scene08_staff_duty_antisliv",
        "tag": "БЕЗОПАСНОСТЬ 3.0 • СИСТЕМА СМЕН",
        "card_title": "НЕПРОБИВАЕМЫЙ СТАФФ-ЩИТ",
        "card_bullets": [
            ("⏱", "Учёт рабочих смен и времени на посту (/duty)"),
            ("⚡️", "Авто-снятие при 3/3 выговорах (сварнах)"),
            ("🔒", "Иммунитет создателя и защита от сливов"),
            ("📊", "Полный журнал аудита наказаний и действий")
        ],
        "voice": (
            "Защита вашей беседы доведена до абсолюта. Система рангов от Стажёра до Создателя чата строго разграничивает "
            "полномочия. Модераторы могут наказывать нарушителей только находясь на официальной рабочей смене по команде "
            "«дьюти». Если модератор грубит участникам или использует нецензурную лексику, бот мгновенно отправляет его "
            "в мут, снимает со смены и выписывает сварн. При трёх нарушениях нерадивый админ снимается с должности "
            "автоматически!"
        ),
        "messages": [
            {
                "sender": "Модератор",
                "text": "/duty",
                "time": "12:07"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "👮‍♂️ ДЕЖУРНАЯ СМЕНА АКТИВИРОВАНА!\n\n"
                    "Модератор: @alex_mod (Ранг: Старший модератор)\n"
                    "Статус: 🟢 НА СМЕНЕ • Таймер запущен\n"
                    "Выговоры: 0/3 (Чистая репутация)\n\n"
                    "🛡 Доступны команды модерации: мут, варн, кик."
                ),
                "buttons": ["🔴 Завершить смену", "📋 Лог действий"],
                "time": "12:07"
            }
        ]
    },
    {
        "id": "scene09_roadmap_future",
        "tag": "РОАДМАП • К ЧЕМУ МЫ ИДЁМ?",
        "card_title": "БУДУЩЕЕ ЭКОСИСТЕМЫ MOXXI",
        "card_bullets": [
            ("💎", "Web3-экономика и вывод наград игрокам"),
            ("🏆", "Межсерверные киберспортивные турниры"),
            ("🎨", "ИИ-генератор аватаров и кастомизация"),
            ("🌍", "Выход на международный рынок (EN, ES, TR)")
        ],
        "voice": (
            "К чему мы идём дальше? Разработка MOXXI не прекращается ни на день. В нашем роадмапе: интеграция безопасной "
            "Web3-экономики с возможностью вывода наград, масштабные межсерверные турниры между сообществами Телеграма и "
            "Дискорда, ИИ-генерация персональных аватаров и кастомизация профилей, а также запуск глобального маркетплейса "
            "игровых предметов. Мы строим самую технологичную платформу для общения в мире!"
        ),
        "messages": [
            {
                "sender": "MOXXI Roadmap",
                "text": (
                    "🚀 ОФИЦИАЛЬНЫЙ РОАДМАП 2026-2027:\n\n"
                    "Q1: Межсерверные клановые турниры (TG + DS)\n"
                    "Q2: Запуск Web3-маркетплейса и артефактов\n"
                    "Q3: ИИ-генератор персональных скинов\n"
                    "Q4: Глобальная экспансия на 5 языках\n\n"
                    "Будущее создаётся прямо сейчас вместе с вами!"
                ),
                "buttons": ["🌟 Поддержать проект", "🗳 Голосовать за фичи"],
                "time": "12:08"
            }
        ]
    },
    {
        "id": "scene10_outro_call_to_action",
        "tag": "ФИНАЛ • ПРИСОЕДИНЯЙСЯ СЕЙЧАС!",
        "card_title": "ДОБАВЬ MOXXI В СВОЮ БЕСЕДУ!",
        "card_bullets": [
            ("✈️", "Бот в Telegram: @moxxichat_bot"),
            ("💬", "Чат сообщества: @moxxi_chat"),
            ("🎮", "Discord-сервер: discord.gg/moxxi"),
            ("🎁", "Секретный промокод: ОБНОВА3.0 (+2.5M)")
        ],
        "voice": (
            "Хватит терпеть устаревших ботов прошлого поколения. Добавьте MOXXI в свою беседу, подключайтесь к нашему "
            "официальному Дискорд-серверу и запускайте Telegram Mini App прямо сейчас! Становитесь лидером своей группы, "
            "побеждайте в рейдах и наслаждайтесь первоклассным общением. Все ссылки ждут вас в описании и закреплённом "
            "комментарии. MOXXI — твоя сила, твой стиль, твоя победа!"
        ),
        "messages": [
            {
                "sender": "MOXXI 3.0",
                "text": (
                    "✨ ПРИСОЕДИНЯЙСЯ К НАМ ПРЯМО СЕЙЧАС!\n\n"
                    "• Telegram: @moxxichat_bot\n"
                    "• Сообщество: @moxxi_chat\n"
                    "• Сервер Discord: discord.gg/moxxi\n\n"
                    "🎁 Не забудьте активировать промокод:\n"
                    "👉 Напишите в чат: промо ОБНОВА3.0\n"
                    "и заберите +2,500,000 монет на свой баланс!"
                ),
                "buttons": ["🚀 Добавить в чат", "💬 Чат сообщества", "🎁 Ввести промо"],
                "time": "12:09"
            }
        ]
    }
]

async def generate_voice_edge(text: str, out_wav: str):
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 10000:
        return
    temp_mp3 = out_wav + ".mp3"
    comm = edge_tts.Communicate(text, "ru-RU-SvetlanaNeural", rate="+5%")
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

def draw_frame(scene_data: dict, progress: float, elapsed_sec: float, total_sec: float, scene_idx: int, total_scenes: int) -> Image.Image:
    # 1. Background (Cyberpunk Deep Slate Blue + Subtle Neon Vignette)
    img = Image.new("RGB", (W, H), "#0b0f19")
    draw = ImageDraw.Draw(img)

    # Gradient glow top banner
    for i in range(120):
        alpha = int(24 * (1 - i / 120))
        draw.line([(0, i), (W, i)], fill=(15 + alpha, 20 + alpha * 2, 40 + alpha * 3))

    # 2. Header Bar
    draw.rectangle([0, 0, W, 64], fill="#0f172a")
    draw.line([0, 64, W, 64], fill="#312e81", width=2)

    # MOXXI Logo / Title
    draw.ellipse([24, 14, 58, 48], fill="#8b5cf6", outline="#c084fc", width=2)
    draw.text((33, 17), "M", font=FONTS["title"], fill="#ffffff")
    draw.text((70, 18), "MOXXI 3.0", font=FONTS["header"], fill="#f8fafc")
    draw.text((188, 22), "•", font=FONTS["header"], fill="#818cf8")
    draw.text((204, 21), "GLOBAL ECOSYSTEM", font=FONTS["small_bold"], fill="#38bdf8")

    # Platform Badges in Header
    platforms = [
        ("✈️ TG Mini App", "#0284c7"),
        ("🎮 Discord Staff", "#5865f2"),
        ("🔷 VKontakte", "#2563eb"),
        ("🟢 MAX", "#16a34a"),
    ]
    px = W - 520
    for p_name, p_col in platforms:
        draw.rounded_rectangle([px, 16, px + 115, 46], radius=6, fill="#1e293b", outline=p_col, width=1)
        draw.text((px + 10, 21), p_name, font=FONTS["badge"], fill="#e2e8f0")
        px += 125

    # 3. Scene Tag & Header
    tag_text = scene_data.get("tag", "MOXXI 3.0")
    tag_w = int(FONTS["badge"].getlength(tag_text)) + 24
    draw.rounded_rectangle([30, 80, 30 + tag_w, 108], radius=6, fill="#3b0764", outline="#a855f7", width=1)
    draw.text((42, 85), tag_text, font=FONTS["badge"], fill="#f3e8ff")

    # 4. Side Feature Showcase Card (Right Column)
    cx, cy, cw, ch = W - 460, 80, 430, 560
    draw.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=16, fill="#111827", outline="#4338ca", width=2)
    
    # Header of card
    draw.rectangle([cx + 2, cy + 2, cx + cw - 2, cy + 52], fill="#1e1b4b")
    draw.text((cx + 18, cy + 14), scene_data["card_title"], font=FONTS["bold"], fill="#fbbf24")
    draw.line([cx, cy + 53, cx + cw, cy + 53], fill="#4338ca", width=1)

    # Bullet points
    by = cy + 74
    for icon, text in scene_data["card_bullets"]:
        draw.ellipse([cx + 18, by, cx + 50, by + 32], fill="#1e293b", outline="#6366f1", width=1)
        draw.text((cx + 25, by + 3), icon, font=FONTS["regular"], fill="#ffffff")
        
        # Word wrap bullet text
        b_lines = []
        cur_line = ""
        for word in text.split(" "):
            test_l = cur_line + " " + word if cur_line else word
            if FONTS["small"].getlength(test_l) > 330:
                b_lines.append(cur_line)
                cur_line = word
            else:
                cur_line = test_l
        if cur_line:
            b_lines.append(cur_line)

        ty = by + 2
        for bl in b_lines:
            draw.text((cx + 62, ty), bl, font=FONTS["small"], fill="#f1f5f9")
            ty += 20
        by += max(44, len(b_lines) * 20 + 26)

    # Status in side card
    draw.line([cx + 16, cy + ch - 65, cx + cw - 16, cy + ch - 65], fill="#1f2937", width=1)
    draw.text((cx + 20, cy + ch - 48), "🟢 Статус: Онлайн 100% • Пинг 35мс", font=FONTS["small_bold"], fill="#4ade80")
    draw.text((cx + 20, cy + ch - 26), f"Сцена {scene_idx + 1} из {total_scenes} • MOXXI 3.0", font=FONTS["badge"], fill="#94a3b8")

    # 5. Chat Messages (Left Column)
    messages = scene_data.get("messages", [])
    if messages:
        y = 125
        for msg in messages:
            sender = msg.get("sender", "User")
            is_user = (sender in ["Создатель", "Игрок", "Модератор"])
            text = msg.get("text", "")
            time_str = msg.get("time", "12:00")
            buttons = msg.get("buttons", [])

            lines = text.split("\n")
            bubble_w = 740
            bubble_h = len(lines) * 23 + 42 + (len(buttons) * 44 if buttons else 0)

            if is_user:
                bx = 30
                draw.rounded_rectangle([bx, y, bx + 360, y + 46], radius=10, fill="#1e3a8a", outline="#3b82f6", width=1)
                draw.text((bx + 14, y + 12), f"{sender}: {text}", font=FONTS["bold"], fill="#93c5fd")
                draw.text((bx + 300, y + 14), f"{time_str} ✓✓", font=FONTS["small"], fill="#bfdbfe")
                y += 58
            else:
                bx = 30
                draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=14, fill="#0f172a", outline="#475569", width=1)
                
                # Avatar & Bot Header
                draw.ellipse([bx + 14, y + 10, bx + 42, y + 38], fill="#9333ea")
                draw.text((bx + 20, y + 11), "M", font=FONTS["bold"], fill="#ffffff")
                draw.text((bx + 52, y + 13), sender, font=FONTS["bold"], fill="#c084fc")
                
                # Official Badge
                draw.rounded_rectangle([bx + 195, y + 14, bx + 242, y + 32], radius=4, fill="#7c3aed")
                draw.text((bx + 202, y + 14), "BOT", font=FONTS["badge"], fill="#ffffff")

                cy_m = y + 44
                for l in lines:
                    color = "#f8fafc"
                    if "⛔️" in l or "🔴" in l or "❌" in l:
                        color = "#f87171"
                    elif "✅" in l or "🟢" in l or "🎉" in l or "ПОБЕДА" in l:
                        color = "#4ade80"
                    elif "💡" in l or "💰" in l or "🎯" in l or "🎁" in l or "👑" in l:
                        color = "#fbbf24"
                    elif "•" in l or "👉" in l:
                        color = "#cbd5e1"
                    draw.text((bx + 18, cy_m), l, font=FONTS["regular"], fill=color)
                    cy_m += 23

                if buttons:
                    cy_m += 6
                    btn_w = (bubble_w - 36 - (len(buttons) - 1) * 10) // len(buttons)
                    for bi, btn in enumerate(buttons):
                        btn_x = bx + 18 + bi * (btn_w + 10)
                        btn_rect = [btn_x, cy_m, btn_x + btn_w, cy_m + 34]
                        draw.rounded_rectangle(btn_rect, radius=8, fill="#1e293b", outline="#6366f1", width=1)
                        t_len = FONTS["small_bold"].getlength(btn)
                        tx_btn = btn_x + max(4, int((btn_w - t_len) / 2))
                        draw.text((tx_btn, cy_m + 7), btn, font=FONTS["small_bold"], fill="#60a5fa")

                y += bubble_h + 14

    # 6. Bottom Progress & Timeline Bar
    draw.rectangle([0, H - 36, W, H], fill="#020617")
    draw.line([0, H - 36, W, H - 36], fill="#1e293b", width=1)

    # Animated Progress Line
    total_prog = min(1.0, max(0.0, elapsed_sec / max(1.0, total_sec)))
    prog_w = int(W * total_prog)
    draw.rectangle([0, H - 36, prog_w, H - 33], fill="#38bdf8")

    # Time counter
    cur_m, cur_s = divmod(int(elapsed_sec), 60)
    tot_m, tot_s = divmod(int(total_sec), 60)
    time_display = f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}"
    draw.text((24, H - 26), time_display, font=FONTS["small_bold"], fill="#94a3b8")

    # Call to action footer
    cta_text = "🚀 MOXXI 3.0: Telegram (@moxxichat_bot) • Discord • VK • MAX | Промокод: ОБНОВА3.0 (+2.500.000 монет)"
    draw.text((W - int(FONTS["badge"].getlength(cta_text)) - 24, H - 24), cta_text, font=FONTS["badge"], fill="#e2e8f0")

    return img

async def main():
    print("=" * 70)
    print("🎬 MOXXI 3.0: BUILDING 5-MINUTE HIGH-DEFINITION MASTER SHOWCASE VIDEO")
    print("=" * 70)

    work_dir = "temp_5min"
    os.makedirs(work_dir, exist_ok=True)

    # 1. Generate Voice for all 10 scenes with edge-tts
    wav_files = []
    durations = []
    print("\n[STEP 1/4] Generating authentic Neural AI voice for 10 scenes...")
    for idx, sc in enumerate(SCENES):
        wav_path = os.path.join(work_dir, f"voice_{sc['id']}.wav")
        print(f"  • Generating Scene {idx+1:02d}/{len(SCENES):02d} [{sc['tag']}]...")
        await generate_voice_edge(sc["voice"], wav_path)
        dur = get_wav_duration(wav_path)
        wav_files.append(wav_path)
        durations.append(dur)
        print(f"    -> Duration: {dur:.1f}s")

    total_video_duration = sum(durations)
    print(f"\n📊 Total Narration Duration: {total_video_duration:.1f}s ({total_video_duration/60:.2f} minutes)")

    # 2. Concat all audio files into one full master track
    print("\n[STEP 2/4] Merging audio tracks into full master track...")
    concat_list = os.path.join(work_dir, "audio_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for w in wav_files:
            f.write(f"file '{os.path.abspath(w)}'\n")

    full_audio = os.path.join(work_dir, "full_5min_audio.wav")
    cmd_concat = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        full_audio
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"✅ Full audio track created: {full_audio}")

    # 3. Direct Pipe Frame Rendering into FFmpeg
    output_mp4 = "MOXXI_5MIN_SHOWCASE_FULL_VIDEO.mp4"
    print(f"\n[STEP 3/4] Rendering frames & streaming into FFmpeg ({W}x{H} @ {FPS} fps)...")

    cmd_ffmpeg = [
        FFMPEG, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",               # Stdin pipe for video frames
        "-i", full_audio,        # Audio track input
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_mp4
    ]

    proc = subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE)

    total_frames = int(total_video_duration * FPS)
    current_frame = 0
    elapsed_time = 0.0

    for sc_idx, sc in enumerate(SCENES):
        sc_dur = durations[sc_idx]
        sc_frames = int(sc_dur * FPS)
        print(f"  • Rendering Scene {sc_idx+1:02d}/{len(SCENES):02d} ({sc_frames} frames)...")

        for f_idx in range(sc_frames):
            sc_prog = f_idx / max(1, sc_frames)
            frame_img = draw_frame(
                sc, sc_prog, elapsed_time, total_video_duration, sc_idx, len(SCENES)
            )
            raw_bytes = frame_img.tobytes()
            proc.stdin.write(raw_bytes)

            current_frame += 1
            elapsed_time += 1.0 / FPS

            if current_frame % (FPS * 15) == 0:
                pct = (current_frame / total_frames) * 100
                print(f"    Progress: {pct:.1f}% ({current_frame}/{total_frames} frames)")

    proc.stdin.close()
    proc.wait()

    # 4. Final verification
    print("\n[STEP 4/4] Verifying generated master video file...")
    if os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 1000000:
        f_size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"🎉 MASTER VIDEO CREATED SUCCESSFULLY!")
        print(f"📁 File: {os.path.abspath(output_mp4)}")
        print(f"📦 Size: {f_size_mb:.2f} MB")
        print(f"⏱ Duration: {total_video_duration:.1f}s ({total_video_duration/60:.2f} minutes)")
    else:
        print(f"❌ Failed to generate video or file size too small!")

if __name__ == "__main__":
    asyncio.run(main())
