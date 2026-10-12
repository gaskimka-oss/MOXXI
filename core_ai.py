"""ИИ-слой бота: анализ чата, проверка справедливости наказаний и умные ответы.

Поддерживает:
  1) Google Gemini (бесплатные ключи AI Studio с авто-ротацией нескольких ключей);
  2) OpenAI / DeepSeek / OpenRouter / Groq (любые совместимые API).

Ключи задаются в .env переменной AI_API_KEY (можно несколько через запятую).
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import urllib.request
import urllib.error

log = logging.getLogger("moxxibot.ai")

# ── Загрузка ключей и конфигурации ──────────────────────────────────────────
_RAW_KEYS = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
KEYS: list[str] = [k.strip() for k in re.split(r"[,;\s]+", _RAW_KEYS) if k.strip()]
_CURRENT_KEY_IDX = 0

KEY = KEYS[0] if KEYS else ""


def _is_gemini_key(k: str) -> bool:
    return k.startswith("AQ.") or k.startswith("AIzaSy")


def _guess_provider_and_model(k: str) -> tuple[str, str, str]:
    """Возвращает (тип_провайдера, url, default_model)."""
    if _is_gemini_key(k):
        return ("gemini", "https://generativelanguage.googleapis.com/v1beta", "gemini-3-flash-preview")
    if k.startswith("sk-or-"):
        return ("openai_compat", "https://openrouter.ai/api/v1/chat/completions", "google/gemma-4-31b-it:free")
    if k.startswith("gsk_"):
        return ("openai_compat", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile")
    if k.startswith("sk-proj-") or k.startswith("sk-svcacct-"):
        return ("openai_compat", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini")
    if k.startswith("sk-"):
        return ("openai_compat", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat")
    return ("gemini" if _is_gemini_key(k) else "openai_compat",
            "https://generativelanguage.googleapis.com/v1beta" if _is_gemini_key(k) else "https://api.openai.com/v1/chat/completions",
            "gemini-3-flash-preview" if _is_gemini_key(k) else "gpt-4o-mini")


_K_SAMPLE = KEYS[0] if KEYS else ""
_PROV_TYPE, _URL_GUESS, _MODEL_GUESS = _guess_provider_and_model(_K_SAMPLE)

PROVIDER_TYPE = os.getenv("AI_PROVIDER_TYPE") or _PROV_TYPE
URL = (os.getenv("AI_API_URL") or _URL_GUESS).strip()
MODEL = (os.getenv("AI_MODEL") or _MODEL_GUESS).strip()
TIMEOUT = int(os.getenv("AI_TIMEOUT", "15") or 15)
_g_models = [MODEL, "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"]
GEMINI_MODELS = list(dict.fromkeys(m for m in _g_models if m))


def available() -> bool:
    return bool(KEYS)


def get_next_key() -> str:
    """Ротация ключей при нескольких добавленных аккаунтах."""
    global _CURRENT_KEY_IDX
    if not KEYS:
        return ""
    k = KEYS[_CURRENT_KEY_IDX % len(KEYS)]
    _CURRENT_KEY_IDX = (_CURRENT_KEY_IDX + 1) % len(KEYS)
    return k


def provider() -> str:
    """Понятное имя сервиса — для команд."""
    if not KEYS:
        return "отключён"
    k_count = len(KEYS)
    count_tag = f" ({k_count} ключ{'а' if 1 < k_count < 5 else 'ей' if k_count >= 5 else ''})" if k_count > 1 else ""
    if _is_gemini_key(KEYS[0]) or "googleapis.com" in URL:
        return f"Google Gemini Flash{count_tag}"
    u = URL.lower()
    for host, name in (("openai", "OpenAI"), ("deepseek", "DeepSeek"),
                       ("openrouter", "OpenRouter"), ("groq", "Groq"),
                       ("mistral", "Mistral"), ("anthropic", "Anthropic"),
                       ("gigachat", "GigaChat"), ("yandex", "YandexGPT")):
        if host in u:
            return f"{name}{count_tag}"
    return f"Пользовательский ИИ{count_tag}"


# ── Вызовы API (Gemini Native + OpenAI Compatible) ──────────────────────────

def _call_gemini_sync(key: str, system: str, user: str, max_tokens: int, temperature: float = 0.0, json_mode: bool = False) -> str | None:
    """Синхронный запрос к Google Gemini REST API с перебором моделей при ошибках."""
    effective_max_tokens = max(max_tokens, 800)
    gen_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": effective_max_tokens,
        "thinkingConfig": {
            "thinkingBudget": 0
        }
    }
    if json_mode:
        gen_config["responseMimeType"] = "application/json"

    # Добавляем жесткую системную инструкцию отвечать строго на русском
    system_text = (system + "\n\nОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ! Твой ответ — только прямая речь, без мыслей или рассуждений на английском.").strip() if system else "ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ!"

    payload: dict = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user[:12000]}]
            }
        ],
        "system_instruction": {
            "parts": [{"text": system_text}]
        },
        "generationConfig": gen_config
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    for m in GEMINI_MODELS:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        req = urllib.request.Request(endpoint, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                candidates = res_data.get("candidates") or []
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts") or []
                if not parts:
                    continue
                # Исключаем служебные мысли ("thought": True) модели Gemini:
                clean_parts = [p for p in parts if not p.get("thought")]
                if not clean_parts:
                    clean_parts = parts
                text = "".join(p.get("text", "") for p in clean_parts).strip()
                # Удаляем служебные теги мыслей, если они попали в текст
                text = re.sub(r"<thought>[\s\S]*?</thought>", "", text, flags=re.IGNORECASE).strip()
                text = re.sub(r"^\*Refining for Moxxi's voice:\*[\s\S]*?\n\n", "", text, flags=re.IGNORECASE).strip()
                if text:
                    return text
        except urllib.error.HTTPError as e:
            if e.code == 400 and "thinkingConfig" in gen_config:
                try:
                    retry_config = dict(gen_config)
                    retry_config.pop("thinkingConfig", None)
                    retry_payload = dict(payload, generationConfig=retry_config)
                    retry_req = urllib.request.Request(endpoint, data=json.dumps(retry_payload).encode("utf-8"), headers=headers)
                    with urllib.request.urlopen(retry_req, timeout=TIMEOUT) as resp2:
                        res_data2 = json.loads(resp2.read().decode("utf-8"))
                        cand2 = res_data2.get("candidates") or []
                        if cand2:
                            pts2 = cand2[0].get("content", {}).get("parts") or []
                            cpts2 = [p for p in pts2 if not p.get("thought")] or pts2
                            t2 = "".join(p.get("text", "") for p in cpts2).strip()
                            if t2:
                                return t2
                except Exception:
                    pass

            if e.code in (404, 429, 503):
                continue
            log.warning("Gemini model %s HTTP %s: %s", m, e.code, str(e)[:120])
        except Exception as e:
            log.warning("Gemini model %s error: %s", m, str(e)[:120])

    return None



def _call_openai_sync(key: str, system: str, user: str, max_tokens: int, temperature: float = 0.0, json_mode: bool = False) -> str | None:
    """Синхронный запрос к OpenAI-совместимому API."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user[:4000]})

    payload: dict = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode and "deepseek" not in URL.lower():
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        res_data = json.load(resp)
        choices = res_data.get("choices") or []
        if not choices:
            return None
        return str(choices[0].get("message", {}).get("content", "")).strip()


def _ask_raw(system: str, user: str, max_tokens: int = 250, temperature: float = 0.0, json_mode: bool = False) -> str | None:
    """Выполняет запрос с перебором ключей при ошибках."""
    if not KEYS:
        return None

    for _ in range(len(KEYS)):
        current_key = get_next_key()
        try:
            if _is_gemini_key(current_key) or "googleapis.com" in URL:
                text = _call_gemini_sync(current_key, system, user, max_tokens, temperature, json_mode)
            else:
                text = _call_openai_sync(current_key, system, user, max_tokens, temperature, json_mode)

            if text:
                return text
        except urllib.error.HTTPError as e:
            log.warning("ИИ HTTP ошибка (%s): %s", e.code, str(e)[:160])
        except Exception as e:
            log.warning("ИИ ошибка вызова: %s", str(e)[:160])

    return None


def _ask_json(system: str, user: str, max_tokens: int = 250) -> dict | None:
    """Запрос с гарантированным парсингом JSON."""
    raw = _ask_raw(system, user, max_tokens, temperature=0.0, json_mode=True)
    if not raw:
        return None
    try:
        return json.loads(raw.strip())
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    log.warning("ИИ вернул не-JSON ответ: %s", raw[:120])
    return None


async def ask(system: str, user: str, max_tokens: int = 250) -> dict | None:
    """Асинхронный JSON-запрос к ИИ."""
    for attempt in (1, 2):
        try:
            res = await asyncio.to_thread(_ask_json, system, user, max_tokens)
            if res is not None:
                return res
        except Exception:
            pass
        if attempt == 1:
            await asyncio.sleep(1.0)
    return None


async def ask_text(prompt: str, system: str = "", max_tokens: int = 800) -> str | None:
    """Асинхронный текстовый ответ на произвольный вопрос."""
    for attempt in (1, 2):
        try:
            res = await asyncio.to_thread(_ask_raw, system, prompt, max_tokens, 0.3)
            if res:
                return res
        except Exception:
            pass
        if attempt == 1:
            await asyncio.sleep(1.0)
    return None


# ══════════════════ ПРАВИЛА СООБЩЕСТВА ══════════════════
COMMUNITY_RULES = """
Обязательные правила сообщества и беседы:
1. Запрещены читы, софты, багоюз, создание помех и руин игр/мероприятий.
2. Общение: вежливость и уважение. Запрещены травля, буллинг, адресные оскорбления и провокация конфликтов.
3. Запрещены спам, реклама сторонних каналов/ботов/ссылок, скам, мошенничество и обман.
4. Запрещены политические и религиозные дискуссии, материалы 18+, деанон и разглашение личных данных.
5. Лестница наказаний:
   • Лёгкие нарушения (капс, флуд, лёгкий оффтоп, мелкая грубость): 1-е — мут 15-60 мин, 2-е — мут 3-6 часов, 3-е — варн.
   • Грубые нарушения (оскорбления, токсичность, мат в адрес участника, помехи): 1-е — 1 варн, 2-е — 2-й варн, 3-е — мут 12-24 часа.
   • Критические (читы, реклама, спам, скам, 18+, деанон): перманентный бан / кик.
6. Обжалование наказаний доступно в боте @moxxichat_bot.
""".strip()
CLAN_RULES = COMMUNITY_RULES


# ══════════════════ 1. НАДЗОР ЗА НАКАЗАНИЯМИ ══════════════════
REVIEW_PROMPT = (
    "Ты — независимый арбитр русскоязычного сообщества и чата. "
    "По переписке, причине и предоставленной истории реши, было ли нарушение "
    "и соответствует ли наказание правилам. Не считай обвинение доказанным "
    "только потому, что оно написано в причине.\n\n"
    + COMMUNITY_RULES + "\n\n"
    "Ответь СТРОГО в JSON:\n"
    '{"verdict": "ok|soft|harsh|wrong", "score": 0-10, '
    '"reason": "одно предложение", "advice": "что стоило сделать"}\n\n'
    "ok — наказание справедливо и выдано строго по правилам (зелёный)\n"
    "soft — нарушение было, но наказание слишком мягкое (синий / сомнения)\n"
    "harsh — нарушение было, но наказание слишком суровое (синий / сомнения)\n"
    "wrong — нарушения не доказано или наказание несправедливо (красный / не согласен)\n"
    "При нехватке контекста снижай score; не выдумывай факты."
)

VERDICT_ICON = {"ok": "🟢", "soft": "🔵", "harsh": "🔵", "wrong": "🔴"}
VERDICT_TEXT = {
    "ok": "Правильно выдан (по правилам)",
    "soft": "Есть сомнения (слишком мягко)",
    "harsh": "Есть сомнения (слишком сурово)",
    "wrong": "Не согласен (ошибка / нарушение правил)",
}


async def review_punishment(kind: str, reason: str, seconds: int,
                            target: str, moderator: str,
                            context: str) -> dict | None:
    """Проверяет наказание. -> {verdict, score, reason, advice} или None."""
    if not available():
        return None
    from core_resolve import human_period
    if seconds:
        term = human_period(seconds)
    elif kind == "warn":
        term = "без срока"
    elif kind == "kick":
        term = "однократно"
    else:
        term = "бессрочно"
    kinds = {"mute": "мут", "ban": "бан", "warn": "предупреждение", "kick": "кик"}
    q = (f"Наказание: {kinds.get(kind, kind)} на {term}\n"
         f"Кого: {target}\n"
         f"Кто выдал: {moderator}\n"
         f"Указанная причина: {reason or '(не указана)'}\n\n"
         f"Переписка перед наказанием:\n{context or '(нет данных)'}")
    res = await ask(REVIEW_PROMPT, q, max_tokens=220)
    if not isinstance(res, dict):
        return None
    v = str(res.get("verdict", "")).lower()
    if v not in VERDICT_ICON:
        return None
    try:
        score = max(0, min(int(res.get("score", 5)), 10))
    except Exception:
        score = 5
    return {"verdict": v, "score": score,
            "reason": str(res.get("reason", ""))[:200],
            "advice": str(res.get("advice", ""))[:200]}


def render_review(r: dict, kind: str, target: str, moderator: str,
                  term: str) -> str:
    """Красивый текст отчёта с цветной индикацией правильности и ссылкой на бота."""
    icon = VERDICT_ICON.get(r["verdict"], "🔵")
    what = VERDICT_TEXT.get(r["verdict"], r["verdict"])
    out = [
        f"🤖 <b>Экспертиза наказания</b>\n",
        f"{icon} <b>Оценка:</b> {what} (уверенность {r['score']}/10)\n",
        f"⚖️ <b>Тип:</b> {kind} · <b>Срок:</b> {term}",
        f"👤 <b>Кому:</b> {target}",
        f"👮 <b>Выдал:</b> {moderator}\n",
        f"📝 <b>Вердикт:</b> {r['reason']}"
    ]
    if r.get("advice") and r["verdict"] != "ok":
        out.append(f"💡 <b>Рекомендация:</b> {r['advice']}")
    out.append(f"\n📩 <i>Обжаловать наказание:</i> <b>@moxxichat_bot</b>")
    return "\n".join(out)


UNPUNISH_REVIEW_PROMPT = (
    "Ты — независимый арбитр и модератор русскоязычной беседы. "
    "Модератор снимает наказание (размут / разбан / снятие варна) с участника. "
    "Оцени причину снятия наказания на адекватность и правомерность.\n\n"
    "Ответь СТРОГО в JSON:\n"
    '{"verdict": "ok|suspicious|wrong", "score": 0-10, '
    '"reason": "краткий вердикт на 1 предложение", "advice": "рекомендация или пусто"}\n\n'
    "ok — причина обоснованная (амнистия, ошибка, исправление, истечение срока)\n"
    "suspicious — причина сомнительная или шуточная (блат, без повода)\n"
    "wrong — грубое нарушение правил или явный саботаж модерации"
)


async def review_unpunish(kind: str, reason: str, target: str,
                          moderator: str) -> dict | None:
    """ИИ-экспертиза снятия наказания."""
    if not available():
        return None
    kinds = {"mute": "снятие мута (размут)", "ban": "снятие бана (разбан)",
             "warn": "снятие предупреждения (варна)"}
    q = (f"Действие: {kinds.get(kind, kind)}\n"
         f"С кого снимается: {target}\n"
         f"Кто снимает: {moderator}\n"
         f"Указанная причина снятия: {reason or '(не указана)'}")
    res = await ask(UNPUNISH_REVIEW_PROMPT, q, max_tokens=180)
    if not isinstance(res, dict):
        return None
    v = str(res.get("verdict", "")).lower()
    return {
        "verdict": v if v in ("ok", "suspicious", "wrong") else "ok",
        "score": int(res.get("score", 7)) if str(res.get("score", "")).isdigit() else 7,
        "reason": str(res.get("reason", ""))[:200],
        "advice": str(res.get("advice", ""))[:200]
    }


def format_ai_verdict(verdict_data: dict) -> str:
    """
    Форматирует ИИ-оценку в едином стандартном виде:
    🟢 Обоснованное действие (амнистия, исправление, ошибка)
    🟡 Сомнительная причина (шуточная причина, возможный блат)
    🔴 Неправомерное действие (нарушение правил модерации)
    """
    if not verdict_data:
        return ""
    v = str(verdict_data.get("verdict", "ok")).lower()
    reason = str(verdict_data.get("reason", "")).strip()

    if v == "ok":
        title = "🟢 <b>Обоснованное действие</b> <i>(амнистия, исправление, ошибка, по правилам)</i>"
    elif v in ("suspicious", "soft", "harsh"):
        title = "🟡 <b>Сомнительная причина</b> <i>(шуточная причина, возможный блат)</i>"
    else:
        title = "🔴 <b>Неправомерное действие</b> <i>(нарушение правил модерации)</i>"

    detail = f"\n   💡 <i>{html.escape(reason)}</i>" if reason else ""
    return f"\n\n🤖 <b>ИИ-контроль:</b>\n{title}{detail}"


async def evaluate_action(kind: str, reason: str, target: str, moderator: str,
                          is_unpunish: bool = False, seconds: int = 0,
                          context: str = "") -> dict:
    """
    Универсальная ИИ-экспертиза действия (наказания или снятия).
    Сначала пробует LLM API, если задан ключ.
    Если ключ не задан или сервис недоступен — запускает умный эвристический арбитраж.
    """
    if available():
        try:
            if is_unpunish:
                res = await review_unpunish(kind, reason, target, moderator)
            else:
                res = await review_punishment(kind, reason, seconds, target, moderator, context)
            if res and res.get("verdict"):
                return res
        except Exception:
            pass

    # Умный эвристический ИИ-анализ (fallback)
    r_low = (reason or "").strip().lower()

    # Сомнительные/шуточные маркеры
    suspicious_words = [
        "шутк", "прикол", "кек", "лол", "кент", "брат", "друг", "красавчик",
        "тест", "проверка", "по приколу", "по фану", "надоел", "бесит", "хз"
    ]
    # Неправомерные/грубые маркеры
    wrong_words = ["123", "хер", "пох", "дурак", "не нравится", "сам такой", "просто"]
    # Обоснованные маркеры для снятия
    valid_unpunish_words = [
        "амнисти", "ошибк", "исправ", "осознал", "пересмотр", "извинил",
        "разбан", "размут", "истек", "помилован", "случайно", "прощен"
    ]
    # Обоснованные маркеры для наказаний
    valid_punish_words = [
        "спам", "реклам", "оск", "мат", "флуд", "капс", "18+", "nsfw",
        "скам", "обман", "чит", "софт", "руин", "деанон", "докс", "токсик",
        "буллинг", "травл", "1.", "2.", "3.", "п."
    ]

    if is_unpunish:
        for w in wrong_words:
            if w in r_low:
                return {"verdict": "wrong", "reason": "Причина снятия не содержит оснований или нарушает регламент."}
        for w in suspicious_words:
            if w in r_low:
                return {"verdict": "suspicious", "reason": "Причина снятия выглядит неформальной или шуточной (возможен блат)."}
        for w in valid_unpunish_words:
            if w in r_low:
                return {"verdict": "ok", "reason": "Обоснованное снятие наказания (амнистия / признание вины / ошибка)."}
        if len(r_low) >= 6:
            return {"verdict": "ok", "reason": "Причина снятия зафиксирована."}
        return {"verdict": "suspicious", "reason": "Слишком короткая причина снятия, требуется контроль администрации."}
    else:
        for w in wrong_words:
            if w in r_low:
                return {"verdict": "wrong", "reason": "Причина не соответствует регламенту наказаний чата."}
        for w in suspicious_words:
            if w in r_low:
                return {"verdict": "suspicious", "reason": "Шуточная или сомнительная причина для наказания."}
        for w in valid_punish_words:
            if w in r_low:
                return {"verdict": "ok", "reason": "Наказание правомерно и соответствует правилам чата."}
        if re.search(r"\b\d+(?:\.\d+)?\b", r_low):
            return {"verdict": "ok", "reason": "Указан пункт правил чата."}
        if len(r_low) >= 8:
            return {"verdict": "ok", "reason": "Причина наказания зафиксирована."}
        return {"verdict": "suspicious", "reason": "Причина требует уточнения по правилам чата."}


# ══════════════════ 2. НАБЛЮДЕНИЕ ЗА ЧАТОМ ══════════════════
WATCH_PROMPT = (
    "Ты модератор русскоязычного сообщества и чата. Проверь ПОСЛЕДНЕЕ сообщение "
    "по КАЖДОМУ правилу, учитывая переписку вокруг него.\n\n"
    + COMMUNITY_RULES + "\n\n"
    "Шкала:\n"
    "0 — нарушения нет;\n"
    "1 — лёгкое: единичный капс/офтоп/грубость/флуд, нужен контекст или "
    "внимание модератора;\n"
    "2 — явное: спам, реклама/сторонняя ссылка, повторный флуд, политическая "
    "или религиозная дискуссия, адресное оскорбление, провокация, помехи;\n"
    "3 — грубое/опасное: угрозы, травля, мошенничество, читы, разглашение "
    "личных данных, материалы 18+.\n\n"
    "Не наказывай цитату правил, жалобу на нарушение, спокойное обжалование, "
    "дружеский подкол или мат без адресата. Если человек "
    "защищается от травли, учитывай зачинщика.\n\n"
    'Ответь СТРОГО в JSON: {"level": 0-3, "category": "правило или норма", '
    '"reason": "кратко", "instigator": "ник зачинщика или пусто"}'
)


async def watch_message(text: str, context: str = "") -> dict | None:
    """Оценка сообщения с учётом переписки."""
    if not available():
        return None
    q = (f"Переписка:\n{context}\n\nПоследнее сообщение: {text[:600]}"
         if context else text[:600])
    res = await ask(WATCH_PROMPT, q, max_tokens=200)
    if not isinstance(res, dict):
        return None
    try:
        lvl = max(0, min(int(res.get("level", 0)), 3))
    except Exception:
        return None
    return {"level": lvl,
            "category": str(res.get("category", ""))[:80],
            "reason": str(res.get("reason", ""))[:120],
            "instigator": str(res.get("instigator", ""))[:64]}


# ══════════════════ 3. СВОДКА ПО ЧАТУ ══════════════════
SUMMARY_PROMPT = (
    "Ты аналитик русскоязычного сообщества и чата. Проверь переписку по всем "
    "правилам ниже и сделай короткую доказательную сводку для владельца. "
    "Не выдумывай нарушения и отличай обсуждение правила от его нарушения.\n\n"
    + COMMUNITY_RULES + "\n\n"
    'Ответь СТРОГО в JSON: {"mood": "спокойно|оживленно|напряженно|конфликт", '
    '"summary": "2-3 предложения о чем говорят", '
    '"problems": "какие правила нарушены и кем, либо пусто", '
    '"advice": "что стоит сделать владельцу по лестнице наказаний, либо пусто"}'
)

MOOD_ICON = {"спокойно": "😌", "оживленно": "🙂", "оживлённо": "🙂",
             "напряженно": "😬", "напряжённо": "😬", "конфликт": "🔥"}


async def chat_summary(context: str) -> dict | None:
    if not available():
        return None
    res = await ask(SUMMARY_PROMPT, context[:3500], max_tokens=320)
    return res if isinstance(res, dict) else None
