"""Меню команд: кнопки разделов + ссылки на telegra.ph с якорями + поиск."""
from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaPhoto, Message)

import db
from config import START_BALANCE
import core_docs as docs
from core_registry import (RANK_NAMES, REGISTRY, SECTION_EMOJI, SECTIONS, Cmd,
                           find_commands, registry_by_section)
from utils import money

router = Router(name="helpmenu")
PER_PAGE = 12

ASSETS = __import__("pathlib").Path(__file__).resolve().parent.parent / "assets"

# какая картинка какому разделу соответствует
SECTION_IMG = {
    **{n: "sec_moderation" for n in (1, 2, 3, 5, 12)},
    **{n: "sec_settings" for n in (4, 6, 7, 10, 11, 26, 28, 32, 40)},
    **{n: "sec_economy" for n in (13, 27, 29, 31, 33, 37, 39, 41)},
    **{n: "sec_games" for n in (14, 15, 16, 34, 36, 43)},
    **{n: "sec_social" for n in (8, 9, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 35, 38, 42, 45)},
}


def _img(name: str):
    for ext in (".jpg", ".png"):
        p = ASSETS / f"{name}{ext}"
        if p.exists():
            return FSInputFile(p)
    return None



CMDS_PER_PAGE = 15

def _all_commands_page(page: int = 0, is_group: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    cmds = [c for c in sorted(REGISTRY, key=lambda c: (c.section, c.rank, c.usage)) if c.section != 40 and c.rank < 10]
    total = max(1, (len(cmds) + CMDS_PER_PAGE - 1) // CMDS_PER_PAGE)
    page = max(0, min(page, total - 1))
    chunk = cmds[page * CMDS_PER_PAGE : (page + 1) * CMDS_PER_PAGE]

    lines = [
        f"📑 <b>ВСЕ КОМАНДЫ БОТА</b> (Стр. <b>{page+1}/{total}</b> — всего: <b>{len(cmds)}</b>)",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]
    for c in chunk:
        rank_badge = f" <i>[{RANK_NAMES.get(c.rank, f'Ранг {c.rank}')}]</i>" if c.rank else ""
        sec_name = SECTIONS.get(c.section, "")
        sec_emoji = SECTION_EMOJI.get(c.section, "•")
        lines.append(
            f"• <code>{html.escape(c.usage)}</code>{rank_badge}\n"
            f"   {html.escape(c.desc)}\n"
            f"   <i>{sec_emoji} {sec_name}</i>"
        )
    lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    lines.append("💡 <i>Поиск: отправьте <code>найти бан</code> или <code>поиск дуэль</code></i>")

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"h:all:{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="h:noop"))
    if page + 1 < total:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"h:all:{page+1}"))

    jump_row = []
    if page > 0:
        jump_row.append(InlineKeyboardButton(text="⏮ В начало", callback_data="h:all:0"))
    if page < total - 1:
        jump_row.append(InlineKeyboardButton(text="В конец ⏭", callback_data=f"h:all:{total-1}"))

    extra_row = [
        InlineKeyboardButton(text="📂 К разделам", callback_data="h:p:0"),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="h:find_prompt"),
    ]
    if is_group:
        extra_row.append(InlineKeyboardButton(text="❌ Закрыть", callback_data="h:close"))

    kb_rows = [nav_row]
    if jump_row:
        kb_rows.append(jump_row)
    kb_rows.append(extra_row)

    if not is_group:
        from core_nav import with_home
        return "\n".join(lines), with_home(InlineKeyboardMarkup(inline_keyboard=kb_rows))
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)

def _menu_kb(page: int = 0, is_group: bool = False, hide_topics: bool = False) -> InlineKeyboardMarkup:
    by_sec = registry_by_section()
    # В одиночном режиме скрываем раздел 10 («Темы модераторов»)
    nums = [n for n in sorted(SECTIONS) if by_sec.get(n) and n != 40 and not (hide_topics and n == 10)]
    total = (len(nums) + PER_PAGE - 1) // PER_PAGE
    chunk = nums[page * PER_PAGE:(page + 1) * PER_PAGE]
    rows, buf = [], []
    rows.append([
        InlineKeyboardButton(text="📑 Все 598 команд (по страницам)", callback_data="h:all:0"),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="h:find_prompt")
    ])
    for n in chunk:
        buf.append(InlineKeyboardButton(
            text=f"{SECTION_EMOJI.get(n,'•')} {SECTIONS[n]}", callback_data=f"h:s:{n}:{page}"))
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf:
        rows.append(buf)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"h:p:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{max(total,1)}", callback_data="h:noop"))
    if page + 1 < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"h:p:{page+1}"))
    rows.append(nav)
    urls = docs.all_urls()
    if len(urls) == 1:
        rows.append([InlineKeyboardButton(text="🌐 Вся справка", url=urls[0]),
                     InlineKeyboardButton(text="🪞 Зеркало",
                                          url=docs.mirror(urls[0]))])
    elif urls:
        # Справка telegra.ph (по 3 кнопки в строке)
        for i in range(0, len(urls), 3):
            chunk = urls[i:i+3]
            rows.append([InlineKeyboardButton(text=f"🌐 Справка ч.{i+j+1}", url=u)
                         for j, u in enumerate(chunk)])
        # Зеркало graph.org для заблокированных стран (Беларусь и др.)
        for i in range(0, len(urls), 3):
            chunk = urls[i:i+3]
            rows.append([InlineKeyboardButton(text=f"🪞 Зеркало ч.{i+j+1}",
                                              url=docs.mirror(u))
                         for j, u in enumerate(chunk)])
    if is_group:
        rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="h:close")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    from core_nav import with_home
    return with_home(InlineKeyboardMarkup(inline_keyboard=rows))


def _menu_text() -> str:
    return (f"📖 <b>Справочник</b> — команд: {len(REGISTRY)}\n\n"
            f"Выберите раздел кнопкой ниже — бот покажет команды прямо здесь.")


def _safe_cut(text: str, limit: int) -> str:
    """Обрезает по границе строки, чтобы не разорвать HTML-тег."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # откатываемся до последнего переноса строки вне тега
    nl = cut.rfind("\n")
    if nl > limit // 2:
        cut = cut[:nl]
    # если остался незакрытый тег — режем до его начала
    lt, gt = cut.rfind("<"), cut.rfind(">")
    if lt > gt:
        cut = cut[:lt]
    return cut.rstrip() + "\n\n<i>…полный список — по кнопке ниже</i>"


def _section_pages(num: int, limit: int = 950) -> list[str]:
    """Разбивает раздел на страницы, чтобы влезть в подпись к фото."""
    cmds = registry_by_section().get(num, [])
    head = f"{SECTION_EMOJI.get(num,'•')} <b>{num}. {SECTIONS[num]}</b>"

    def block(c, syn: bool, desc: bool) -> str:
        line = f"• <code>{html.escape(c.usage)}</code>"
        if c.rank:
            line += f" <i>(ранг {c.rank})</i>"
        if desc and c.desc:
            line += f"\n   {html.escape(c.desc)}"
        if syn and len(c.names) > 1:
            line += f"\n   <i>синонимы: {html.escape(', '.join(c.names[1:6]))}</i>"
        return line

    # подбираем детализацию: сначала подробно, потом ужимаем
    for syn, desc in ((True, True), (False, True), (False, False)):
        blocks = [block(c, syn, desc) for c in cmds]
        pages, cur = [], head
        for b in blocks:
            if len(cur) + len(b) + 2 > limit:
                pages.append(cur)
                cur = head + "\n"
            cur += "\n" + b
        pages.append(cur)
        if len(pages) <= 6:      # не больше 6 страниц на раздел
            return pages
    return pages


def _section_text(num: int, limit: int = 1000) -> str:
    """Текст раздела. Автоматически сжимается, чтобы влезть в подпись к фото."""
    cmds = registry_by_section().get(num, [])
    head = f"{SECTION_EMOJI.get(num,'•')} <b>{num}. {SECTIONS[num]}</b>\n"

    def render(with_syn: bool, with_desc: bool) -> str:
        out = [head]
        for c in cmds:
            line = f"• <code>{html.escape(c.usage)}</code>"
            if c.rank:
                line += f" <i>(ранг {c.rank})</i>"
            if with_desc and c.desc:
                line += f"\n   {html.escape(c.desc)}"
            if with_syn and len(c.names) > 1:
                line += f"\n   <i>синонимы: {html.escape(', '.join(c.names[1:6]))}</i>"
            out.append(line)
        return "\n".join(out)

    for syn, desc in ((True, True), (False, True), (False, False)):
        t = render(syn, desc)
        if len(t) <= limit:
            return t
    return _safe_cut(render(False, False), limit - 60)


@router.message(CommandStart())
async def cmd_start(message: Message):
    u = await db.get_user(message.from_user.id)
    await message.answer(
        f"👋 Привет, {html.escape(message.from_user.first_name or '')}!\n\n"
        f"Модерация, ранги, экономика, игры и десятки модулей.\n"
        f"🍬 Ваш баланс: <b>{money(u['balance'])}</b>\n\n"
        f"📖 Все команды — /команды\n"
        f"🩺 Проверить права в группе — /проверка")
    photo = _img("banner_main")
    if photo:
        try:
            return await message.answer_photo(photo, caption=_menu_text(),
                                              reply_markup=_menu_kb(0))
        except Exception:
            pass
    await message.answer(_menu_text(), reply_markup=_menu_kb(0))


@router.message(Cmd("команды", "помощь", "хелп", "help", "start", section=32,
                    usage="команды [номер_страницы]", desc="Меню всех команд бота"))
async def cmd_help(message: Message, args: str = "", **kw):
    is_group = message.chat.type != "private"
    hide_topics = False
    if is_group:
        from h_chatset import get_effective_chat_mode
        mode = await get_effective_chat_mode(message.chat.id, getattr(message.chat, "is_forum", False))
        hide_topics = (mode == "single")

    a = (args or "").strip()
    if a.isdigit():
        page = max(0, int(a) - 1)
        txt, kb = _all_commands_page(page, is_group=is_group)
        photo = _img("sec_moderation")
        if photo:
            try:
                return await message.answer_photo(photo, caption=txt, reply_markup=kb)
            except Exception:
                pass
        return await message.answer(txt, reply_markup=kb, disable_web_page_preview=True)

    kb = _menu_kb(0, is_group=is_group, hide_topics=hide_topics)
    txt = _menu_text()
    photo = _img("banner_main")
    if photo:
        try:
            return await message.answer_photo(photo, caption=txt, reply_markup=kb)
        except Exception:
            pass
    await message.answer(txt, reply_markup=kb, disable_web_page_preview=True)


async def _edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup, img: str):
    """Меняет и картинку, и подпись — работает для фото- и текстовых сообщений."""
    if call.message.photo:
        photo = _img(img)
        if photo:
            try:
                return await call.message.edit_media(
                    InputMediaPhoto(media=photo, caption=text[:1024]), reply_markup=kb)
            except Exception:
                pass
        try:
            return await call.message.edit_caption(caption=text[:1024], reply_markup=kb)
        except Exception:
            pass
    try:
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await call.message.answer(text, reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("h:"))
async def cb_help(call: CallbackQuery):
    parts = call.data.split(":")
    if parts[1] == "noop":
        return await call.answer()
    if parts[1] == "close":
        try:
            await call.message.delete()
        except Exception:
            await call.answer("Справочник закрыт")
        return

    is_group = call.message.chat.type != "private"
    hide_topics = False
    if is_group:
        from h_chatset import get_effective_chat_mode
        mode = await get_effective_chat_mode(call.message.chat.id, getattr(call.message.chat, "is_forum", False))
        hide_topics = (mode == "single")

    if parts[1] == "all":
        page = int(parts[2]) if len(parts) > 2 else 0
        txt, kb = _all_commands_page(page, is_group=is_group)
        await _edit(call, txt, kb, "sec_moderation")
        return await call.answer()

    if parts[1] == "find_prompt":
        return await call.answer(
            "🔍 Отправьте в чат:\nнайти [слово]\nНапример: найти бан или найти дуэль",
            show_alert=True
        )

    if parts[1] == "p":
        page = int(parts[2])
        await _edit(call, _menu_text(), _menu_kb(page, is_group=is_group, hide_topics=hide_topics), "banner_main")
        return await call.answer()

    if parts[1] == "s":
        num, page = int(parts[2]), int(parts[3])
        sub = int(parts[4]) if len(parts) > 4 else 0
        pages = _section_pages(num)
        sub = max(0, min(sub, len(pages) - 1))
        url = docs.section_url(num)
        rows = []
        if len(pages) > 1:
            nav = []
            if sub > 0:
                nav.append(InlineKeyboardButton(
                    text="◀️", callback_data=f"h:s:{num}:{page}:{sub-1}"))
            nav.append(InlineKeyboardButton(
                text=f"{sub+1}/{len(pages)}", callback_data="h:noop"))
            if sub + 1 < len(pages):
                nav.append(InlineKeyboardButton(
                    text="▶️", callback_data=f"h:s:{num}:{page}:{sub+1}"))
            rows.append(nav)
        if url:
            rows.append([
                InlineKeyboardButton(text="🔗 Раздел в справке", url=url),
                InlineKeyboardButton(text="🪞 Зеркало",
                                     url=docs.mirror(url))])
        if is_group:
            rows.append([InlineKeyboardButton(text="⬅️ К разделам", callback_data=f"h:p:{page}")])
            rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="h:close")])
            await _edit(call, pages[sub], InlineKeyboardMarkup(inline_keyboard=rows),
                        SECTION_IMG.get(num, "banner_main"))
        else:
            from core_nav import with_home
            await _edit(call, pages[sub],
                        with_home(InlineKeyboardMarkup(inline_keyboard=rows),
                                  back=f"h:p:{page}", back_text="⬅️ К разделам"),
                        SECTION_IMG.get(num, "banner_main"))
        return await call.answer()
    await call.answer()


@router.message(Cmd("найти", "поиск команды", "поиск", "найти команду", "find", "search", section=32,
                    usage="найти {слово}", desc="Поиск команды по названию"))
async def cmd_find(message: Message, args: str = "", **kw):
    q = (args or "").strip()
    if not q:
        return await message.reply("Формат: <code>найти бан</code> или <code>найти дуэль</code>")
    found = find_commands(q)
    if not found:
        return await message.reply(f"Ничего не найдено по «{html.escape(q)}».")
    out = [f"🔎 Найдено: <b>{len(found)}</b>\n"]
    for c in found[:15]:
        rank_str = f" <i>[{RANK_NAMES.get(c.rank, f'Ранг {c.rank}')}]</i>" if c.rank else ""
        out.append(f"• <code>{html.escape(c.usage)}</code>{rank_str} — {html.escape(c.desc)}\n"
                   f"   <i>Раздел: {SECTIONS.get(c.section,'')}</i>")
    from core_nav import with_home
    rows = []
    if found:
        url = docs.section_url(found[0].section)
        if url:
            rows.append([InlineKeyboardButton(text="🔗 Открыть в справке", url=url)])
    rows.append([InlineKeyboardButton(text="📑 Все команды (по страницам)", callback_data="h:all:0")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.reply(_safe_cut("\n".join(out), 3800),
                        reply_markup=with_home(kb),
                        disable_web_page_preview=True)


@router.message(Cmd("справка", "докs", "документация", section=32, usage="справка",
                    desc="Ссылка на полную справку"))
async def cmd_docs(message: Message, **kw):
    urls = docs.all_urls()
    if not urls:
        return await message.reply("Справка ещё не опубликована.")
    body = "\n".join(f"• Часть {i+1}: {u}" for i, u in enumerate(urls))
    mirr = "\n".join(f"• Часть {i+1}: {docs.mirror(u)}"
                     for i, u in enumerate(urls))
    await message.reply(
        f"📖 <b>Полная справка по командам</b>\n{body}\n\n"
        f"🪞 <b>Если не открывается</b> (Беларусь и др.):\n{mirr}",
        disable_web_page_preview=True)


@router.message(Cmd("обновить справку", section=32, rank=5, usage="обновить справку",
                    desc="Перегенерировать справку (владелец)"))
async def cmd_docs_update(message: Message, bot: Bot, **kw):
    from core_ranks import require
    if not await require(message, bot, 5):
        return
    m = await message.reply("⏳ Публикую справку…")
    try:
        import asyncio
        st = await asyncio.to_thread(docs.publish)
        await m.edit_text(f"✅ Справка обновлена:\n{st['url']}")
    except Exception as e:
        await m.edit_text(f"⚠️ Ошибка: {html.escape(str(e))}")
