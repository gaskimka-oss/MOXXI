# -*- coding: utf-8 -*-
"""
MOXXI 3.0 - OFFICIAL 5-MINUTE PLAYER SHOWCASE VIDEO (TIKTOK & YOUTUBE)
100% PLAYER ORIENTED • NO STAFF COMMANDS • 4 PLATFORMS ROLLOUT

Highlighting:
1. Scene 1: MOXXI 3.0 Global Launch on 4 Platforms (Telegram, Discord, VK, MAX)
2. Scene 2: The Evolution: Why MOXXI Destroys Iris and Legacy Bots
3. Scene 3: Casino 3.0: Roulette x36, Slots, Crash, Mines & Jackpots
4. Scene 4: Financial Empire: 40 Businesses, Bank Deposits & Stock Market
5. Scene 5: Social & Romance: Weddings, Kids, Pets & Families
6. Scene 6: World Boss Raids, Weapon Crafting & High-Stakes PvP
7. Scene 7: Clans, City District Wars & Tournaments
8. Scene 8: AI Copilot: Instant Voice & Video Circle STT + Gemini AI
9. Scene 9: Player Support, Bug Bounty & Community Ideas Bank
10. Scene 10: How to Add MOXXI, Community Links & Starter Promo Code

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
        "id": "scene01_launch_4platforms",
        "tag": "ГЛОБАЛЬНЫЙ РЕЛИЗ • 4 ПЛАТФОРМЫ",
        "card_title": "MOXXI 3.0: МЫ ВЕЗДЕ!",
        "card_bullets": [
            ("✈️", "Telegram: Флагманский бот и неоновый Mini App"),
            ("🎮", "Discord: Игровой бот и 24/7 хаб поддержки"),
            ("🔷", "ВКонтакте: Полная экосистема для бесед"),
            ("⚡️", "MAX Messenger: Скоростной кроссплатформенный мост")
        ],
        "voice": (
            "Встречайте грандиозное событие года! Официальный глобальный релиз игрового бота нового поколения — "
            "MOXXI три точка ноль! Мы вышли сразу на четыре крупнейшие площадки: Телеграм с великолепным Mini App "
            "приложением, Дискорд с игровыми серверами и круглосуточной поддержкой, социальную сеть ВКонтакте и "
            "современный мессенджер MAX! Играйте вместе с друзьями там, где удобно вам, с единым игровым прогрессом "
            "и молниеносным откликом!"
        ),
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
                    "🌐 Платформы: Telegram • Discord • VK • MAX\n"
                    "🏢 Предприятия: 40/40 под контролем\n\n"
                    "Выберите раздел игры:"
                ),
                "buttons": ["🎰 Казино 3.0", "🐉 Рейды на боссов", "🏢 Мои бизнесы"],
                "time": "12:00"
            }
        ]
    },
    {
        "id": "scene02_moxxi_vs_iris",
        "tag": "БИТВА ТЕХНОЛОГИЙ • MOXXI VS IRIS",
        "card_title": "ПОЧЕМУ MOXXI РАЗРЫВАЕТ ИРИС?",
        "card_bullets": [
            ("❌", "Ирис: Устаревший текст 2018 года без инлайн-кнопок"),
            ("✅", "MOXXI: Неоновый UI, Mini App, нажатия в 1 клик"),
            ("❌", "Ирис: Вечные лаги, медленный отклик и скука"),
            ("✅", "MOXXI: Мгновенная облачная скорость и 100+ игр")
        ],
        "voice": (
            "Почему сотни тысяч игроков и бесед массово бросают Ирис и переходят на MOXXI? Разница видна невооружённым "
            "глазом! Ирис застрял в далёком две тысячи восемнадцатом году: унылые серые простыни монохромного текста, "
            "нулевой интерактив и постоянные зависания. В MOXXI вас встречает сочный неоновый дизайн, управление "
            "кнопками в один клик, полноценный Web App, искусственный интеллект и постоянные масштабные обновления каждую "
            "неделю. Будущее уже наступило!"
        ),
        "messages": [
            {
                "sender": "Сравнение",
                "text": (
                    "📊 ЧЕМ MOXXI ПРЕВОСХОДИТ СТАРЫХ БОТОВ:\n\n"
                    "🔴 ИРИС БОТ:\n"
                    "• Серая простыня текста без единой кнопки\n"
                    "• 0% нейросетей и нет распознавания войсов\n"
                    "• Только текстовые команды из прошлого века\n\n"
                    "🟢 MOXXI 3.0:\n"
                    "• Интерактивные inline-кнопки и Web App\n"
                    "• Google Gemini AI + перевод ГС и кружков\n"
                    "• 4 платформы и единая экономика"
                ),
                "buttons": ["🏆 Играть на MOXXI 3.0"],
                "time": "12:01"
            }
        ]
    },
    {
        "id": "scene03_casino_games",
        "tag": "АЗАРТ И ЭМОЦИИ • КАЗИНО 3.0",
        "card_title": "ЗОЛОТОЕ КАЗИНО & МИНИ-ИГРЫ",
        "card_bullets": [
            ("🎲", "Европейская рулетка x36 на инлайн-кнопках"),
            ("🎰", "Слоты с Джекпотом и анимацией барабанов"),
            ("💣", "Мины с выбором ловушек и Краш с иксами"),
            ("🔐", "Взлом Сейфа с гигантским общим банком")
        ],
        "voice": (
            "Испытайте настоящий азарт в Казино три точка ноль! Вас ждёт полноценная Европейская рулетка на тридцать "
            "шесть чисел с выплатами до тридцати шести к одному, анимированные слоты с джекпотом, захватывающий Краш "
            "с высокими коэффициентами и игра Мины, где вы сами настраиваете уровень риска. А взлом секретного сейфа "
            "позволит сорвать рекордный куш, накопленный всеми игроками сообщества!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "краш 500000",
                "time": "12:02"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🚀 КРАШ РАКЕТА MOXXI ВЗЛЕТЕЛА!\n\n"
                    "📈 Текущий множитель: x4.82 🔥\n"
                    "💰 Ваш выигрыш: 2,410,000 монет!\n\n"
                    "🎉 УСПЕШНЫЙ ЗАБОР! Ракета продолжает полёт!\n"
                    "💵 Новый баланс: 27,410,000 монет"
                ),
                "buttons": ["🚀 Запустить ещё", "🎰 В слоты", "💣 В мины"],
                "time": "12:02"
            }
        ]
    },
    {
        "id": "scene04_economy_businesses",
        "tag": "ФИНАНСЫ • ИМПЕРИЯ БИЗНЕСОВ",
        "card_title": "40 ПРЕДПРИЯТИЙ & БАНК",
        "card_bullets": [
            ("🏢", "40 уникальных бизнесов: от кофейни до IT-гиганта"),
            ("📈", "Пассивный доход каждый час прямо на баланс"),
            ("🏦", "Банковские вклады с процентами и сложным ростом"),
            ("📊", "Биржа акций и крипторынок с живыми курсами")
        ],
        "voice": (
            "Постройте собственную финансовую империю! В MOXXI доступно сорок видов предприятий: начните со скромного "
            "придорожного кафе или автомойки и дорастите до владельца собственной нефтедобывающей вышки, сети космических "
            "спутников и квантовой корпорации. Получайте пассивный доход каждый час, инвестируйте прибыль в банковские "
            "депозиты под процент и торгуйте акциями на бирже!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "бизнесы",
                "time": "12:03"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🏢 ВАША БИЗНЕС-ИМПЕРИЯ (38/40):\n\n"
                    "1. ☕️ Сеть кофеен «Moxxi Bean» — Доход: 45,000/час\n"
                    "2. ⚡️ Дата-центр ИИ «Gemini Core» — Доход: 280,000/час\n"
                    "3. 🛢 Нефтяной синдикат «Apex Oil» — Доход: 950,000/час\n\n"
                    "💵 Общая прибыль: +1,275,000 монет в час!\n"
                    "📦 На складах: продукция на 4,800,000 монет"
                ),
                "buttons": ["💰 Собрать прибыль", "📈 Улучшить бизнесы", "🏦 В банк"],
                "time": "12:03"
            }
        ]
    },
    {
        "id": "scene05_romance_family",
        "tag": "ОТНОШЕНИЯ • СЕМЬЯ И ПИТОМЦЫ",
        "card_title": "СВАДЬБЫ, ДЕТИ И ПИТОМЦЫ",
        "card_bullets": [
            ("💍", "Свадьбы с кольцами и пышными церемониями"),
            ("👶", "Воспитание детей и совместное семейное имущество"),
            ("🦊", "Питомцы: кормите, прокачивайте и получайте баффы"),
            ("💞", "Десятки романтических и дружеских РП-действий")
        ],
        "voice": (
            "Общение в MOXXI наполнено теплом и живыми эмоциями. Найдите свою вторую половинку, сыграйте пышную "
            "свадьбу с обручальными кольцами, обустройте семейный особняк и заведите детей. А милые питомцы — от "
            "верных щенков до сказочных дракончиков — будут радовать вас каждый день, принося ценный опыт, бонусы к "
            "доходу и защищая семью!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "брак @eva_star",
                "time": "12:04"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "💍 ПРЕДЛОЖЕНИЕ РУКИ И СЕРДЦА!\n\n"
                    "👤 @cyber_hero сделал романтическое предложение @eva_star!\n"
                    "💎 Подарено: Бриллиантовое кольцо бесконечности ✨\n\n"
                    "💞 Семейный статус: Счастливый брак (День 1)\n"
                    "🐾 Питомец семьи: Огненный Лис «Феникс» (Уровень 12)"
                ),
                "buttons": ["💖 Принять предложение", "🏡 Семейный дом", "🐾 Питомец"],
                "time": "12:04"
            }
        ]
    },
    {
        "id": "scene06_boss_raids_pvp",
        "tag": "БИТВЫ И РЕЙДЫ • МИРОВЫЕ БОССЫ",
        "card_title": "РЕЙД-БОССЫ И ДУЭЛИ 1 НА 1",
        "card_bullets": [
            ("🐉", "Мировые боссы 4 раза в день с фазами ярости"),
            ("⚔️", "PvP дуэли с реальными ставками против игроков"),
            ("🛡", "Крафт оружия, броня, артефакты и заточка снаряжения"),
            ("🎁", "Эпический лут, редкие трофеи и сундуки победы")
        ],
        "voice": (
            "Жаждете жарких сражений? Четыре раза в день в MOXXI пробуждаются гигантские Мировые Боссы: Древние Драконы, "
            "Титаны Бездны и Кибернетические Големы! Объединяйтесь всем чатом, бейте по уязвимым точкам босса и забирайте "
            "легендарное оружие и редкие кристаллы. А на арене дуэлей докажите личное превосходство в поединках один на один "
            "с миллионными ставками!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "босс атака",
                "time": "12:05"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "⚔️ КРИТИЧЕСКИЙ УДАР ПО МИРОВОМУ ДРАКОНУ!\n\n"
                    "💥 Вы нанесли: 185,400 урона (Меч Бездны +12)!\n"
                    "🩸 Здоровье босса: [██████░░░░] 62%\n\n"
                    "🎁 Получено за удар: +350,000 монет и 250 XP!\n"
                    "🏆 Ваше место в рейде: Топ 1 по нанесённому урону"
                ),
                "buttons": ["⚔️ Ударить снова", "🛡 Сменить оружие", "🏆 Таблица рейда"],
                "time": "12:05"
            }
        ]
    },
    {
        "id": "scene07_clans_districts",
        "tag": "КЛАНОВЫЕ ВОЙНЫ • СИНДИКАТЫ",
        "card_title": "КЛАНЫ И ЗАХВАТ ГОРОДСКИХ РАЙОНОВ",
        "card_bullets": [
            ("👑", "Создание клана, казна, флаги и командный чат"),
            ("🏙", "Захват районов мегаполиса и сбор налогов"),
            ("🏆", "Масштабные турниры кланов с огромным призовым фондом"),
            ("🤝", "Клановые альянсы, союзы и войны за влияние")
        ],
        "voice": (
            "Создайте свой могущественный синдикат и подчините себе мегаполис! Развивайте клановую базу, пополняйте "
            "общую казну, объявляйте войны соперникам и захватывайте городские районы, приносящие ежедневные налоговые "
            "сборы каждому участнику. Участвуйте в межсерверных турнирах и приведите свой клан на вершину мирового "
            "рейтинга славы!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "клан",
                "time": "12:06"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "👑 КЛАН 『LEGION』 • РЕЙТИНГ: ТОП 1 МИРА\n\n"
                    "Лидер: @cyber_hero • Участников: 50/50\n"
                    "🏦 Казна клана: 142,000,000 монет\n"
                    "🏙 Под контролем: 4 района («Центр», «Порт», «Сити»)\n"
                    "💵 Ежедневный налог с районов: +6,500,000 монет\n\n"
                    "🛡 Активный статус: Война с кланом 『PHANTOM』"
                ),
                "buttons": ["🏙 Карта районов", "⚔️ В атаку на клан", "🏦 Казна"],
                "time": "12:06"
            }
        ]
    },
    {
        "id": "scene08_ai_voice_stt",
        "tag": "НЕЙРОСЕТИ • GOOGLE GEMINI AI",
        "card_title": "ИИ-КОПИЛОТ И РАСПОЗНАВАНИЕ РЕЧИ",
        "card_bullets": [
            ("🎙", "Мгновенный перевод голосовых и видео-кружков в текст"),
            ("🧠", "Нейросетевой собеседник по команде «ии [вопрос]»"),
            ("📝", "Помощь в учёбе, кодинге и генерации историй"),
            ("⚡️", "Умные подсказки и ответы за долю секунды")
        ],
        "voice": (
            "Искусственный интеллект в MOXXI делает ваше общение невероятно удобным. Устали слушать длинные "
            "голосовые сообщения или смотреть видео-кружочки в шумных местах? Бот мгновенно переводит любые войсы "
            "в аккуратный читаемый текст! А встроенная нейросеть Google Gemini ответит на любой ваш вопрос, поможет решить "
            "сложную задачу или составит классное поздравление!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "🎤 [Голосовое сообщение 0:18]",
                "time": "12:07"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎙 РАСПОЗНАННЫЙ ТЕКСТ ГОЛОСОВОГО:\n\n"
                    "«Привет всем! Собираем пати на штурм\n"
                    "Древнего Дракона в теме боссов через 10 минут!»\n\n"
                    "⚡️ Переведено нейросетью MOXXI STT • Время: 0.4 сек"
                ),
                "buttons": ["🤖 Спросить ИИ", "⚔️ Идти на рейд"],
                "time": "12:07"
            }
        ]
    },
    {
        "id": "scene09_support_and_ideas",
        "tag": "СЛУЖБА ЗАБОТЫ • БАНК ИДЕЙ И БАГ-БАУНТИ",
        "card_title": "НАШЛИ БАГ? ЕСТЬ ИДЕЯ? НАПИШИТЕ!",
        "card_bullets": [
            ("🆘", "Нашли баг? Напишите в чат: поддержка [описание] или баг [текст]"),
            ("💡", "Крутая идея? Напишите прямо в чат: идея [текст вашей идеи]"),
            ("🎮", "Discord Поддержка 24/7: discord.gg/7hDq4R2q"),
            ("🎁", "Щедрые награды: миллионы монет и VIP за лучшие идеи!")
        ],
        "voice": (
            "Мы ценим каждого игрока и делаем MOXXI лучше вместе с вами! Если вы столкнулись с ошибкой или багом — "
            "просто напишите прямо в любой чат команду «поддержка» или «баг» с описанием проблемы. А если у вас родилась "
            "крутая идея для обновления — введите команду «идея» и текст предложения! Ваше обращение моментально поступит "
            "разработчикам и администрации в Telegram и Discord. Мы быстро всё исправим, а за ценные находки и отличные "
            "идеи щедро награждаем миллионами монет, эксклюзивными значками и VIP-статусом!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "идея добавить межсерверные турниры по покеру",
                "time": "12:08"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "💡 ВАША ИДЕЯ УСПЕШНО ОТПРАВЛЕНА РАЗРАБОТЧИКАМ!\n\n"
                    "📝 Суть: «Межсерверные турниры по покеру»\n"
                    "⚡️ Статус: 🟢 Передано в команду разработки\n\n"
                    "🎁 Награда: Если идея попадёт в обновление, вам\n"
                    "будет начислено +5,000,000 монет и статус Новатора!\n\n"
                    "Также вы можете писать в Discord: discord.gg/7hDq4R2q"
                ),
                "buttons": ["💡 Предложить ещё", "💬 Чат игроков", "🎮 Наш Discord"],
                "time": "12:08"
            }
        ]
    },
    {
        "id": "scene10_outro_promocode",
        "tag": "СТАРТ • ПРИСОЕДИНЯЙСЯ СЕЙЧАС!",
        "card_title": "ДОБАВЬ MOXXI И ЗАБЕРИ 2.500.000!",
        "card_bullets": [
            ("✈️", "Telegram бот: @moxxichat_bot"),
            ("💬", "Официальное комьюнити: @moxxi_chat"),
            ("🎮", "Discord сервер: discord.gg/7hDq4R2q"),
            ("🎁", "Секретный промокод: ОБНОВА3.0 (+2.500.000 монет)")
        ],
        "voice": (
            "Пора играть на новом уровне! Добавьте MOXXI в свою беседу в Телеграме, подключайте бота на сервере в Дискорде, "
            "в беседах ВКонтакте и в мессенджере MAX! Прямо сейчас напишите в чат команду «промо ОБНОВА три точка ноль» "
            "и мгновенно заберите два с половиной миллиона бонусных монет на свой баланс! Все ссылки ждут вас в описании. "
            "MOXXI — твоя игра, твои правила, твоя победа!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "промо ОБНОВА3.0",
                "time": "12:09"
            },
            {
                "sender": "MOXXI",
                "text": (
                    "🎉 ПРОМОКОД «ОБНОВА3.0» УСПЕШНО АКТИВИРОВАН!\n\n"
                    "💰 На ваш баланс начислено: +2,500,000 монет!\n"
                    "👑 Вы получили статус: Первопроходец 3.0\n\n"
                    "🚀 Добавьте MOXXI во все свои беседы и серверы:\n"
                    "• Telegram: @moxxichat_bot • Чат: @moxxi_chat\n"
                    "• Discord: discord.gg/7hDq4R2q"
                ),
                "buttons": ["🚀 Добавить в чат", "💬 Чат сообщества", "🎮 Discord Сервер"],
                "time": "12:09"
            }
        ]
    }
]

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
    draw.text((204, 21), "4 ПЛАТФОРМЫ: TG • DISCORD • VK • MAX", font=FONTS["small_bold"], fill="#38bdf8")

    # Platform Badges in Header
    platforms = [
        ("✈️ Telegram", "#0284c7"),
        ("🎮 Discord", "#5865f2"),
        ("🔷 ВКонтакте", "#2563eb"),
        ("⚡️ MAX", "#16a34a"),
    ]
    px = W - 520
    for p_name, p_col in platforms:
        draw.rounded_rectangle([px, 16, px + 115, 46], radius=6, fill="#1e293b", outline=p_col, width=1)
        draw.text((px + 12, 21), p_name, font=FONTS["badge"], fill="#e2e8f0")
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
    draw.text((cx + 20, cy + ch - 48), "🟢 Статус: Онлайн 100% • 4 Платформы", font=FONTS["small_bold"], fill="#4ade80")
    draw.text((cx + 20, cy + ch - 26), f"Раздел {scene_idx + 1} из {total_scenes} • MOXXI 3.0", font=FONTS["badge"], fill="#94a3b8")

    # 5. Chat Messages (Left Column)
    messages = scene_data.get("messages", [])
    if messages:
        y = 125
        for msg in messages:
            sender = msg.get("sender", "User")
            is_user = (sender in ["Игрок", "Сравнение"])
            text = msg.get("text", "")
            time_str = msg.get("time", "12:00")
            buttons = msg.get("buttons", [])

            lines = text.split("\n")
            bubble_w = 740
            bubble_h = len(lines) * 23 + 42 + (len(buttons) * 44 if buttons else 0)

            if is_user:
                bx = 30
                draw.rounded_rectangle([bx, y, bx + 420, y + 46], radius=10, fill="#1e3a8a", outline="#3b82f6", width=1)
                draw.text((bx + 14, y + 12), f"{sender}: {text}", font=FONTS["bold"], fill="#93c5fd")
                draw.text((bx + 360, y + 14), f"{time_str} ✓✓", font=FONTS["small"], fill="#bfdbfe")
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
    print("🎬 MOXXI 3.0: GENERATING BRAND NEW 5-MINUTE PLAYER SHOWCASE (100% PLAYER)")
    print("=" * 70)

    work_dir = "temp_player_5min"
    os.makedirs(work_dir, exist_ok=True)

    # 1. Generate Voice for all 10 scenes with edge-tts
    wav_files = []
    durations = []
    print("\n[STEP 1/4] Generating authentic Neural AI voice for 10 player scenes...")
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

    full_audio = os.path.join(work_dir, "full_player_audio.wav")
    cmd_concat = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        full_audio
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"✅ Full audio track created: {full_audio}")

    # 3. Direct Pipe Frame Rendering into FFmpeg
    output_mp4 = "MOXXI_5MIN_PLAYER_OFFICIAL_VIDEO.mp4"
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
        print(f"🎉 MASTER PLAYER PROMO VIDEO CREATED SUCCESSFULLY!")
        print(f"📁 File: {os.path.abspath(output_mp4)}")
        print(f"📦 Size: {f_size_mb:.2f} MB")
        print(f"⏱ Duration: {total_video_duration:.1f}s ({total_video_duration/60:.2f} minutes)")
    else:
        print(f"❌ Failed to generate video or file size too small!")

if __name__ == "__main__":
    asyncio.run(main())
