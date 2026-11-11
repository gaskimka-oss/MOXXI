# -*- coding: utf-8 -*-
"""
MOXXI 3.0 - OFFICIAL 5-MINUTE PLAYER SHOWCASE VIDEO (720p HD)
100% PLAYER-ORIENTED • ZERO STAFF COMMANDS • 4 PLATFORMS ROLLOUT
• Voice Engine: Microsoft Pavel (Windows OneCore Native Neural Russian Male) - Instant & 100% Consistent
• Zero Raw Links in Video (All links referenced to description)
• Accurate Discord Architecture: Support & Ticket Hub + Bot Commands (No general chat claim)
• Visual Platform Tour: Telegram -> VK & MAX -> Discord Embeds
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
import winsdk.windows.media.speechsynthesis as ws
import winsdk.windows.storage.streams as streams

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
FPS = 15

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

def is_emoji_char(char: str) -> bool:
    code = ord(char)
    if code <= 0x024F or (0x0400 <= code <= 0x052F):
        return False
    return True

def render_mixed_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font_key: str, fill: str):
    font = FONTS.get(font_key, FONTS["regular"])
    emj_font = EMOJI_FONTS.get(font_key, EMOJI_FONTS["regular"])
    cur_x = x
    chunk = ""
    is_curr_emoji = None
    for char in text:
        char_is_emj = is_emoji_char(char)
        if is_curr_emoji is None:
            is_curr_emoji = char_is_emj
            chunk = char
        elif char_is_emj == is_curr_emoji:
            chunk += char
        else:
            f = emj_font if is_curr_emoji else font
            draw.text((cur_x, y), chunk, font=f, fill=fill)
            cur_x += int(f.getlength(chunk))
            is_curr_emoji = char_is_emj
            chunk = char
    if chunk:
        f = emj_font if is_curr_emoji else font
        draw.text((cur_x, y), chunk, font=f, fill=fill)
        cur_x += int(f.getlength(chunk))
    return cur_x - x

def get_mixed_text_width(text: str, font_key: str) -> int:
    font = FONTS.get(font_key, FONTS["regular"])
    emj_font = EMOJI_FONTS.get(font_key, EMOJI_FONTS["regular"])
    total_w = 0
    chunk = ""
    is_curr_emoji = None
    for char in text:
        char_is_emj = is_emoji_char(char)
        if is_curr_emoji is None:
            is_curr_emoji = char_is_emj
            chunk = char
        elif char_is_emj == is_curr_emoji:
            chunk += char
        else:
            f = emj_font if is_curr_emoji else font
            total_w += int(f.getlength(chunk))
            is_curr_emoji = char_is_emj
            chunk = char
    if chunk:
        f = emj_font if is_curr_emoji else font
        total_w += int(f.getlength(chunk))
    return total_w

SCENES = [
    {
        "id": "scene01_launch_4platforms",
        "tag": "🔥 ГЛОБАЛЬНЫЙ РЕЛИЗ • 4 ПЛАТФОРМЫ",
        "card_title": "MOXXI 3.0: МЫ ВЕЗДЕ!",
        "card_bullets": [
            ("✈️", "Telegram: Флагманский бот и неоновый Mini App"),
            ("🎮", "Discord: Игровой бот и 24/7 тикет-поддержка"),
            ("🔷", "ВКонтакте: Полная экосистема для бесед"),
            ("⚡️", "Макс: Скоростной кроссплатформенный мост")
        ],
        "voice": (
            "Всем огромный привет, друзья! Вы долго ждали этого события, и оно наконец-то свершилось! "
            "Состоялся масштабный запуск игрового бота Мокси три точка ноль! Теперь наша игровая вселенная "
            "работает сразу на четырёх крупнейших площадках: во флагманском Телеграме с удобнейшим Мини Аппом, "
            "в Дискорде с игровым ботом и круглосуточной тикет-поддержкой, в беседах ВКонтакте и в современном мессенджере Макс! "
            "Играйте с друзьями там, где вам комфортно, а все ссылки на ботов уже ждут вас в описании под этим видео!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "старт",
                "time": "12:00"
            },
            {
                "sender": "MOXXI 3.0",
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
    },
    {
        "id": "scene02_tg_flagship_vs_iris",
        "tag": "⚡️ TELEGRAM • ФЛАГМАНСКИЙ БОТ",
        "card_title": "ПОЧЕМУ MOXXI ЛУЧШЕ СТАРЫХ БОТОВ?",
        "card_bullets": [
            ("❌", "Старые боты: Скучный серый текст без инлайн-кнопок"),
            ("✅", "MOXXI: Неоновый UI, Mini App, нажатия в 1 клик"),
            ("❌", "Старые боты: Постоянные лаги и медленный отклик"),
            ("✅", "MOXXI: Мгновенная облачная скорость и 100+ игр")
        ],
        "voice": (
            "Начнём наш обзор с Телеграма — главного флагмана проекта! Почему сотни тысяч игроков и бесед "
            "выбирают Мокси вместо устаревших ботов? Разница видна сразу! Старые боты застряли в прошлом: "
            "скучные серые простыни текста, ноль интерактива и постоянные лаги. В Мокси вас встречает "
            "сочный неоновый интерфейс, удобное управление кнопками в один клик, полноценный Веб Апп, "
            "умный искусственный интеллект и регулярные обновления каждую неделю!"
        ),
        "messages": [
            {
                "sender": "Сравнение",
                "text": (
                    "📊 ЧЕМ MOXXI ПРЕВОСХОДИТ СТАРЫХ БОТОВ:\n\n"
                    "🔴 СТАРЫЕ БОТЫ:\n"
                    "• Серая простыня текста без единой кнопки\n"
                    "• 0% нейросетей и нет распознавания войсов\n"
                    "• Только команды из прошлого века\n\n"
                    "🟢 MOXXI 3.0 В TELEGRAM:\n"
                    "• Интерактивные inline-кнопки и Web App\n"
                    "• Искусственный интеллект + перевод ГС и кружков\n"
                    "• Единый баланс на всех 4 платформах"
                ),
                "buttons": ["🏆 Играть в Telegram"],
                "time": "12:01"
            }
        ]
    },
    {
        "id": "scene03_casino_games",
        "tag": "🎰 АЗАРТ И ЭМОЦИИ • КАЗИНО 3.0",
        "card_title": "ЗОЛОТОЕ КАЗИНО & МИНИ-ИГРЫ",
        "card_bullets": [
            ("🎲", "Европейская рулетка x36 на инлайн-кнопках"),
            ("🎰", "Слоты с Джекпотом и анимацией барабанов"),
            ("💣", "Мины с выбором ловушек и Краш с иксами"),
            ("🔐", "Взлом Сейфа с гигантским общим банком")
        ],
        "voice": (
            "Любите азарт и яркие эмоции? Добро пожаловать в Казино три точка ноль! "
            "Вас ждёт европейская рулетка на тридцать шесть чисел с выплатами до тридцати шести к одному, "
            "анимированные слоты с растущим джекпотом, динамичная ракета Краш с высокими коэффициентами "
            "и тактическая игра Мины, где вы сами настраиваете сложность. "
            "А взломав секретный сейф, можно сорвать колоссальный куш, собранный всеми игроками!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "краш 500000",
                "time": "12:02"
            },
            {
                "sender": "MOXXI 3.0",
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
        "tag": "🏢 ФИНАНСЫ • ИМПЕРИЯ БИЗНЕСОВ",
        "card_title": "40 ПРЕДПРИЯТИЙ & БАНК",
        "card_bullets": [
            ("🏢", "40 уникальных бизнесов: от кофейни до IT-гиганта"),
            ("📈", "Пассивный доход каждый час прямо на баланс"),
            ("🏦", "Банковские вклады с процентами и сложным ростом"),
            ("📊", "Биржа акций и крипторынок с живыми курсами")
        ],
        "voice": (
            "Постройте собственную бизнес-империю с нуля! В Мокси доступно сорок видов предприятий: "
            "начните со скромного придорожного кафе или автомойки и дойдите до нефтяных вышек, дата-центров "
            "искусственного интеллекта и космических корпораций! Получайте стабильный пассивный доход каждый час, "
            "открывайте вклады в банке под высокий процент и зарабатывайте миллионы монет на бирже акций!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "бизнесы",
                "time": "12:03"
            },
            {
                "sender": "MOXXI 3.0",
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
        "tag": "💍 ОТНОШЕНИЯ • СЕМЬЯ И ПИТОМЦЫ",
        "card_title": "СВАДЬБЫ, ДЕТИ И ПИТОМЦЫ",
        "card_bullets": [
            ("💍", "Свадьбы с кольцами и пышными церемониями"),
            ("👶", "Воспитание детей и совместное семейное имущество"),
            ("🦊", "Питомцы: кормите, прокачивайте и получайте баффы"),
            ("💞", "Десятки романтических и дружеских РП-действий")
        ],
        "voice": (
            "Мокси — это не просто игра, это тёплое и живое общение! Найдите свою вторую половинку, "
            "сделайте красивое романтическое предложение руки и сердца, сыграйте пышную свадьбу и обустройте "
            "семейный дом. А верные питомцы — от забавных щенков до сказочных дракончиков — будут расти вместе с вами, "
            "принося приятные бонусы к доходу, ценный опыт и защищая семью!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "брак @eva_star",
                "time": "12:04"
            },
            {
                "sender": "MOXXI 3.0",
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
        "tag": "⚔️ БИТВЫ И РЕЙДЫ • МИРОВЫЕ БОССЫ",
        "card_title": "РЕЙД-БОССЫ И ДУЭЛИ 1 НА 1",
        "card_bullets": [
            ("🐉", "Мировые боссы 4 раза в день с фазами ярости"),
            ("⚔️", "PvP дуэли с реальными ставками против игроков"),
            ("🛡", "Крафт оружия, броня, артефакты и заточка снаряжения"),
            ("🎁", "Эпический лут, редкие трофеи и сундуки победы")
        ],
        "voice": (
            "Для любителей жарких сражений каждый день проходят рейды на могучих Мировых Боссов! "
            "Объединяйтесь всем чатом, бейте Древнего Дракона и Титана Бездны, забирайте легендарное оружие, "
            "редкие артефакты и ценные кристаллы. А на арене дуэлей бросайте вызов другим игрокам и выигрывайте "
            "миллионные ставки в честных поединках один на один!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "босс атака",
                "time": "12:05"
            },
            {
                "sender": "MOXXI 3.0",
                "text": (
                    "⚔️ КРИТИЧЕСКИЙ УДАР ПО МИРОВОМУ ДРАКОНУ!\n\n"
                    "💥 Вы нанесли: 185,400 урона (Меч Бездны +12)!\n"
                    "🩸 Здоровье босса: [██████░░░░] 62%\n\n"
                    "🎁 Получено за удар: +350,000 монет и 250 опыта!\n"
                    "🏆 Ваше место в рейде: Топ 1 по нанесённому урону"
                ),
                "buttons": ["⚔️ Ударить снова", "🛡 Сменить оружие", "🏆 Таблица рейда"],
                "time": "12:05"
            }
        ]
    },
    {
        "id": "scene07_clans_districts",
        "tag": "👑 КЛАНОВЫЕ ВОЙНЫ • СИНДИКАТЫ",
        "card_title": "КЛАНЫ И ЗАХВАТ ГОРОДСКИХ РАЙОНОВ",
        "card_bullets": [
            ("👑", "Создание клана, казна, флаги и командный чат"),
            ("🏙", "Захват районов мегаполиса и сбор налогов"),
            ("🏆", "Масштабные турниры кланов с огромным призовым фондом"),
            ("🤝", "Клановые альянсы, союзы и войны за влияние")
        ],
        "voice": (
            "Хотите править целым мегаполисом? Создавайте свой клан или вступайте в ряды сильнейших синдикатов! "
            "Развивайте клановую базу, пополняйте общую казну и захватывайте городские районы, чтобы каждый день "
            "получать налоговые сборы. Сражайтесь в масштабных межсерверных войнах и поднимите свой клан на первую строчку "
            "мирового рейтинга славы!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "клан",
                "time": "12:06"
            },
            {
                "sender": "MOXXI 3.0",
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
        "id": "scene08_vk_and_max",
        "tag": "🔷 ВКОНТАКТЕ & МАКС • БОТЫ В БЕСЕДАХ",
        "card_title": "БОТЫ ДЛЯ VK И МЕССЕНДЖЕРА МАКС",
        "card_bullets": [
            ("🔷", "ВКонтакте: Официальный бот для бесед и сообществ"),
            ("⚡️", "Макс: Мгновенный отклик и поддержка всех команд"),
            ("🎙", "Распознавание голосовых сообщений и кружков"),
            ("🔄", "Полная синхронизация прогресса с Telegram")
        ],
        "voice": (
            "А теперь переместимся во ВКонтакте и современный мессенджер Макс! Если вы общаетесь в беседах "
            "ВКонтакте или переписываетесь в Максе — вам не нужно никуда переходить! Просто добавьте нашего официального "
            "бота в свою беседу. Здесь доступны все те же игры, казино, дуэли, кланы и умное распознавание голосовых "
            "сообщений. Ваш игровой профиль и баланс сохраняются общими между всеми платформами!"
        ),
        "messages": [
            {
                "sender": "Игрок в VK",
                "text": "профиль",
                "time": "12:07"
            },
            {
                "sender": "MOXXI VK & МАКС",
                "text": (
                    "🔷 ОФИЦИАЛЬНЫЙ БОТ MOXXI ДЛЯ БЕСЕД:\n\n"
                    "👤 Игрок: @cyber_hero (ID: 928172)\n"
                    "💰 Баланс: 27,410,000 монет (Синхронизирован)\n"
                    "🏆 Статус: VIP Platinum • Клан: 『LEGION』\n\n"
                    "🎙 Распознавание войсов в беседе: Включено ✅\n"
                    "⚡️ Отклик бота: 0.12 сек"
                ),
                "buttons": ["🎰 Казино в беседе", "🏢 Мои бизнесы", "👑 Клан"],
                "time": "12:07"
            }
        ]
    },
    {
        "id": "scene09_discord_support_bot",
        "tag": "🎮 DISCORD • ИГРОВОЙ БОТ & ПОДДЕРЖКА",
        "card_title": "ДИСКОРД: БОТ & ТИКЕТ-СИСТЕМА 24/7",
        "card_bullets": [
            ("🎮", "Игровой Discord-бот: слэш-команды прямо на сервере"),
            ("🎫", "Тикет-система: круглосуточная связь со стаффом"),
            ("🆘", "Нашли баг? Напишите /поддержка или /баг"),
            ("💡", "Есть идея? Команда /идея с щедрой наградой!")
        ],
        "voice": (
            "В Дискорде мы запустили полноценного игрового бота и официальный центр заботы о пользователях! "
            "Обратите внимание: наш Дискорд создан как специализированный хаб поддержки и сервер игрового бота, "
            "где дежурная администрация решает любые вопросы через удобные тикеты. "
            "Нашли баг или хотите предложить идею для обновления? Введите слэш-команду «поддержка», «баг» или «идея»! "
            "Ваш тикет моментально поступит стаффу, а за полезные идеи мы щедро дарим миллионы монет и эксклюзивные статусы!"
        ),
        "messages": [
            {
                "sender": "Игрок в Discord",
                "text": "/поддержка Нашли редкий сундук в рейде",
                "time": "12:08"
            },
            {
                "sender": "MOXXI SUPPORT BOT",
                "text": (
                    "🎫 ТИКЕТ В ТЕХПОДДЕРЖКУ УСПЕШНО СОЗДАН!\n\n"
                    "📁 Платформа: Discord • Статус: 🟢 Передано стаффу\n"
                    "📝 Обращение: «Нашли редкий сундук в рейде»\n\n"
                    "⚡️ Дежурный модератор ответит вам прямо в тикете.\n"
                    "🎁 За ценные идеи начисляется до +5,000,000 монет!"
                ),
                "buttons": ["🎫 Мой тикет", "💡 Предложить идею", "🎮 Игровые команды"],
                "time": "12:08"
            }
        ]
    },
    {
        "id": "scene10_outro_promocode",
        "tag": "🚀 СТАРТ • ПРИСОЕДИНЯЙСЯ СЕЙЧАС!",
        "card_title": "ЗАБЕРИ 2.500.000 МОНЕТ ПРЯМО СЕЙЧАС!",
        "card_bullets": [
            ("🎁", "Секретный промокод: ОБНОВА3.0 (+2.500.000 монет)"),
            ("✈️", "Telegram: Флагманский бот и чат сообщества"),
            ("🎮", "Discord: Игровой бот и 24/7 тикет-поддержка"),
            ("🔗", "Все ссылки на подключение ждут вас в описании!")
        ],
        "voice": (
            "Присоединяйтесь к нашей игровой вселенной прямо сейчас! Добавляйте ботов в свои чаты и беседы: "
            "во флагманский Телеграм, на серверы в Дискорде, в беседы ВКонтакте и в мессенджер Макс! "
            "Прямо сейчас напишите в чат команду «промо ОБНОВА три точка ноль» и мгновенно заберите "
            "два с половиной миллиона бонусных монет на свой баланс! "
            "Все официальные ссылки на ботов и сообщество ждут вас в описании под этим видео. "
            "Мокси — твоя игра, твои правила, твоя победа!"
        ),
        "messages": [
            {
                "sender": "Игрок",
                "text": "промо ОБНОВА3.0",
                "time": "12:09"
            },
            {
                "sender": "MOXXI 3.0",
                "text": (
                    "🎉 ПРОМОКОД «ОБНОВА3.0» УСПЕШНО АКТИВИРОВАН!\n\n"
                    "💰 На ваш баланс начислено: +2,500,000 монет!\n"
                    "👑 Вы получили статус: Первопроходец 3.0\n\n"
                    "🚀 Добавьте MOXXI во все свои беседы и серверы!\n"
                    "🔗 Все официальные ссылки ждут вас в описании под видео!"
                ),
                "buttons": ["🚀 Добавить в чат", "💬 Сообщество", "🎮 Discord Поддержка"],
                "time": "12:09"
            }
        ]
    }
]

USER_VOICE_OGG = r"C:\Users\eiema\OneDrive\Desktop\2basess\audio_2026-11-11_05-13-23.ogg"
PIPER_MODEL = r"piper_models/ru_RU-denis-medium.onnx"
PIPER_CONFIG = r"piper_models/ru_RU-denis-medium.onnx.json"

_piper_voice = None

def get_piper_voice():
    global _piper_voice
    if _piper_voice is None:
        os.environ['ESPEAK_DATA_PATH'] = r'C:\piper_data'
        from piper.voice import PiperVoice
        _piper_voice = PiperVoice.load(PIPER_MODEL, config_path=PIPER_CONFIG)
    return _piper_voice

def synthesize_piper_denis(text: str, out_wav: str):
    """
    Synthesizes natural, human-sounding Russian speech using Piper Neural TTS (Denis).
    Fast offline generation in ~1.5s per scene.
    """
    voice = get_piper_voice()
    temp_raw = out_wav + ".raw.wav"
    with wave.open(temp_raw, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(voice.config.sample_rate)
        for chunk in voice.synthesize(text):
            wf.writeframes(chunk.audio_int16_bytes)

    # Master audio: warm broadcast compressor + presence EQ to match studio mic
    cmd = [
        FFMPEG, "-y", "-i", temp_raw,
        "-af", "volume=1.1,acompressor=threshold=-16dB:ratio=2.5:attack=15:release=120,equalizer=f=3500:width_type=h:width=1200:g=1.5",
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
        out_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(temp_raw):
        try:
            os.remove(temp_raw)
        except Exception:
            pass

def generate_scene1_hybrid_voice(out_wav: str, work_dir: str):
    """
    Uses the user's authentic voice recording for the opening greeting of Scene 1,
    then seamlessly transitions to natural narrator voice for the platforms breakdown.
    """
    if os.path.exists(USER_VOICE_OGG):
        print("  ⭐ User Voice Sample found! Integrating authentic voice into Scene 1...", flush=True)
        user_part_wav = os.path.join(work_dir, "scene01_user_part.wav")
        # Clean & master user voice: noise suppression, gentle compression, EQ matching
        cmd_user = [
            FFMPEG, "-y", "-i", USER_VOICE_OGG,
            "-af", "highpass=f=70,lowpass=f=12000,afftdn=nr=10:nf=-35,volume=1.35,acompressor=threshold=-16dB:ratio=2.5:attack=15:release=120,equalizer=f=3500:width_type=h:width=1200:g=2.0",
            "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
            user_part_wav
        ]
        subprocess.run(cmd_user, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Narrator continuation
        continuation_text = (
            "крупнейших площадках: во флагманском Телеграме с удобнейшим Мини Аппом, "
            "в Дискорде с игровым ботом и круглосуточной тикет-поддержкой, "
            "в беседах ВКонтакте и в современном мессенджере Макс! "
            "Играйте с друзьями там, где вам комфортно, а все ссылки на ботов уже ждут вас в описании под этим видео!"
        )
        cont_part_wav = os.path.join(work_dir, "scene01_cont_part.wav")
        synthesize_piper_denis(continuation_text, cont_part_wav)

        # Concatenate user intro + continuation
        concat_list = os.path.join(work_dir, "scene01_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            f.write(f"file '{os.path.abspath(user_part_wav)}'\n")
            f.write(f"file '{os.path.abspath(cont_part_wav)}'\n")

        cmd_cat = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            out_wav
        ]
        subprocess.run(cmd_cat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        synthesize_piper_denis(SCENES[0]["voice"], out_wav)

def get_wav_duration(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as w:
        return w.getnframes() / float(w.getframerate())

def draw_frame(scene_data: dict, progress: float, elapsed_sec: float, total_sec: float, scene_idx: int, total_scenes: int) -> Image.Image:
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
    render_mixed_text(draw, cx + 36, cy + ch - 44, "Серверы: Онлайн 100% • 4 Платформы", "small_bold", "#4ade80")
    render_mixed_text(draw, cx + 20, cy + ch - 22, f"Эпизод {scene_idx + 1} из {total_scenes} • MOXXI 3.0", "badge", "#94a3b8")

    # 5. Left Column: Chat Simulation Cards
    messages = scene_data.get("messages", [])
    if messages:
        y = 124
        for msg in messages:
            sender = msg.get("sender", "User")
            is_user = ("Игрок" in sender or "Сравнение" in sender)
            is_discord = ("Discord" in sender or "DISCORD" in sender)
            text = msg.get("text", "")
            time_str = msg.get("time", "12:00")
            buttons = msg.get("buttons", [])

            lines = text.split("\n")
            bubble_w = 750
            bubble_h = len(lines) * 23 + 46 + (len(buttons) * 44 if buttons else 0)

            if is_user:
                bx = 32
                user_card_w = 500
                user_bg = "#172554" if not is_discord else "#1e1f29"
                user_border = "#2563eb" if not is_discord else "#5865f2"
                draw.rounded_rectangle([bx, y, bx + user_card_w, y + 46], radius=10, fill=user_bg, outline=user_border, width=1)
                
                # User Avatar
                draw.ellipse([bx + 10, y + 8, bx + 38, y + 36], fill=user_border)
                render_mixed_text(draw, bx + 17, y + 10, "👤", "small", "#ffffff")
                
                # Text
                render_mixed_text(draw, bx + 48, y + 12, f"{sender}: {text}", "bold", "#93c5fd")
                render_mixed_text(draw, bx + user_card_w - 60, y + 14, f"{time_str} ✓✓", "small", "#60a5fa")
                y += 58
            else:
                bx = 32
                card_bg = "#0e1626" if not is_discord else "#141624"
                card_border = "#334155" if not is_discord else "#5865f2"
                draw.rounded_rectangle([bx, y, bx + bubble_w, y + bubble_h], radius=14, fill=card_bg, outline=card_border, width=1)
                
                # Discord Embed Left Stripe if discord scene
                if is_discord:
                    draw.rounded_rectangle([bx + 2, y + 2, bx + 8, y + bubble_h - 2], radius=4, fill="#5865f2")

                # Bot Header
                avatar_color = "#7c3aed" if not is_discord else "#5865f2"
                draw.ellipse([bx + 16, y + 10, bx + 44, y + 38], fill=avatar_color, outline="#c084fc", width=1)
                draw.text((bx + 22, y + 11), "M", font=FONTS["bold"], fill="#ffffff")
                render_mixed_text(draw, bx + 54, y + 13, sender, "bold", "#c084fc" if not is_discord else "#818cf8")
                
                # Verification Pill Badge
                draw.rounded_rectangle([bx + 215, y + 13, bx + 355, y + 33], radius=4, fill="#1e1b4b", outline="#6366f1", width=1)
                render_mixed_text(draw, bx + 223, y + 14, "✓ БОТ ВЕРИФИЦИРОВАН", "badge", "#a5b4fc")

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
                    elif "⚡️" in l or "🌐" in l or "🔗" in l:
                        color = "#38bdf8"
                    render_mixed_text(draw, bx + 22, cy_m, l, "regular", color)
                    cy_m += 23

                if buttons:
                    cy_m += 6
                    btn_w = (bubble_w - 44 - (len(buttons) - 1) * 12) // len(buttons)
                    for bi, btn in enumerate(buttons):
                        btn_x = bx + 22 + bi * (btn_w + 12)
                        btn_bg = "#1e1b4b" if not is_discord else "#1e1f38"
                        btn_outline = "#6366f1" if not is_discord else "#5865f2"
                        draw.rounded_rectangle([btn_x, cy_m, btn_x + btn_w, cy_m + 34], radius=8, fill=btn_bg, outline=btn_outline, width=1)
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

    # Clean Rolling Banner (NO RAW URLS)
    cta_text = "🎁 Промокод на +2.500.000 монет: ОБНОВА3.0 | 4 Платформы: TG • DS • VK • Макс | Все ссылки в описании под видео!"
    render_mixed_text(draw, W - get_mixed_text_width(cta_text, "badge") - 24, H - 26, cta_text, "badge", "#38bdf8")

    return img

async def main():
    print("=" * 70, flush=True)
    print("🎬 MOXXI 3.0: 5-MINUTE PLAYER SHOWCASE (100% PLAYER ORIENTED)", flush=True)
    print("⚡️ Voice Engine: User Authentic Intro Voice + Piper Denis (Natural Human Voice)", flush=True)
    print("⚡️ Clean: Zero raw links | Discord: Support & Bot Hub (No chat claims)", flush=True)
    print("=" * 70, flush=True)

    work_dir = "temp_player_5min"
    os.makedirs(work_dir, exist_ok=True)

    # Clean old audio to ensure 100% consistent Pavel voice across all 10 scenes
    for old_f in os.listdir(work_dir):
        try:
            os.remove(os.path.join(work_dir, old_f))
        except Exception:
            pass

    # 1. Generate Voice for all 10 scenes with native Windows OneCore Pavel
    wav_files = []
    durations = []
    print("\n[STEP 1/4] Generating natural human voice (User Authentic Intro + Piper Denis)...", flush=True)
    for idx, sc in enumerate(SCENES):
        wav_path = os.path.join(work_dir, f"voice_{sc['id']}.wav")
        print(f"  • Generating Scene {idx+1:02d}/{len(SCENES):02d} [{sc['tag']}]...", flush=True)
        if idx == 0:
            generate_scene1_hybrid_voice(wav_path, work_dir)
        else:
            synthesize_piper_denis(sc["voice"], wav_path)
        dur = get_wav_duration(wav_path)
        wav_files.append(wav_path)
        durations.append(dur)
        print(f"    -> Duration: {dur:.1f}s", flush=True)

    total_video_duration = sum(durations)
    print(f"\n📊 Total Narration Duration: {total_video_duration:.1f}s ({total_video_duration/60:.2f} minutes)", flush=True)

    # 2. Concat all audio files into one full master track
    print("\n[STEP 2/4] Merging audio tracks into full master track...", flush=True)
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
    print(f"✅ Full audio track created: {full_audio}", flush=True)

    # 3. Direct Pipe Frame Rendering into FFmpeg
    output_mp4 = "MOXXI_5MIN_PLAYER_OFFICIAL_VIDEO.mp4"
    print(f"\n[STEP 3/4] Rendering frames & streaming into FFmpeg ({W}x{H} @ {FPS} fps)...", flush=True)

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
        print(f"  • Rendering Scene {sc_idx+1:02d}/{len(SCENES):02d} ({sc_frames} frames)...", flush=True)

        for f_idx in range(sc_frames):
            sc_prog = f_idx / max(1, sc_frames)
            frame_img = draw_frame(
                sc, sc_prog, elapsed_time, total_video_duration, sc_idx, len(SCENES)
            )
            raw_bytes = frame_img.tobytes()
            proc.stdin.write(raw_bytes)

            current_frame += 1
            elapsed_time += 1.0 / FPS

            if current_frame % (FPS * 10) == 0:
                pct = (current_frame / total_frames) * 100
                print(f"    [PROGRESS] {pct:.1f}% ({current_frame}/{total_frames} frames)", flush=True)

    proc.stdin.close()
    proc.wait()

    # 4. Final verification
    print("\n[STEP 4/4] Verifying generated master video file...", flush=True)
    if os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 1000000:
        f_size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"🎉 MASTER PLAYER PROMO VIDEO CREATED SUCCESSFULLY!", flush=True)
        print(f"📁 File: {os.path.abspath(output_mp4)}", flush=True)
        print(f"📦 Size: {f_size_mb:.2f} MB", flush=True)
        print(f"⏱ Duration: {total_video_duration:.1f}s ({total_video_duration/60:.2f} minutes)", flush=True)
    else:
        print(f"❌ Failed to generate video or file size too small!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
