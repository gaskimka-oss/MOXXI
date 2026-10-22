import asyncio
import urllib.request
import urllib.parse
import json
import re

WEATHER_CODES = {
    0: "Ясно ☀️",
    1: "Преимущественно ясно 🌤",
    2: "Переменная облачность ⛅️",
    3: "Пасмурно ☁️",
    45: "Туман 🌫",
    48: "Осаждающий иней / туман 🌫",
    51: "Лёгкая морось 🌦",
    53: "Умеренная морось 🌦",
    55: "Плотная морось 🌧",
    56: "Ледяная морось 🌧",
    57: "Сильная ледяная морось 🌧",
    61: "Небольшой дождь 🌧",
    63: "Умеренный дождь 🌧",
    65: "Сильный ливень 🌧🌧",
    66: "Ледяной дождь 🌨",
    67: "Сильный ледяной дождь 🌨",
    71: "Небольшой снегопад 🌨",
    73: "Умеренный снегопад ❄️",
    75: "Сильный снегопад ❄️❄️",
    77: "Снежные зёрна 🌨",
    80: "Кратковременный дождь 🌦",
    81: "Ливень 🌧⚡️",
    82: "Шквальный ливень 🌊⚡️",
    85: "Снегопад 🌨",
    86: "Сильный снежный шквал ❄️🌪",
    95: "Гроза ⛈",
    96: "Гроза с небольшим градом ⛈❄️",
    99: "Гроза с сильным градом ⛈💥",
}

KNOWN_CITIES = {
    "углегорск": (48.31488, 38.27179, "г. Углегорск (ДНР)"),
    "углегорск днр": (48.31488, 38.27179, "г. Углегорск (ДНР)"),
    "углегорск сахалин": (49.0799, 142.06876, "г. Углегорск (Сахалин)"),
    "донецк": (48.0159, 37.8028, "г. Донецк (ДНР)"),
    "макеевка": (48.0436, 37.9614, "г. Макеевка (ДНР)"),
    "горловка": (48.3061, 38.0264, "г. Горловка (ДНР)"),
    "енакиево": (48.2215, 38.2054, "г. Енакиево (ДНР)"),
    "дебальцево": (48.3377, 38.4184, "г. Дебальцево (ДНР)"),
    "москва": (55.7522, 37.6156, "г. Москва"),
    "санкт-петербург": (59.9386, 30.3141, "г. Санкт-Петербург"),
    "питер": (59.9386, 30.3141, "г. Санкт-Петербург"),
    "ростов": (47.2357, 39.7015, "г. Ростов-на-Дону"),
}


def is_weather_query(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(w in low for w in ("погод", "температур", "градус", "дождь", "снег", "жара", "холод"))


def extract_city(text: str) -> tuple[str, bool]:
    low = text.lower()
    if "углегорск" in low:
        if "сахалин" in low:
            return "углегорск сахалин", True
        return "углегорск", True
    if "донецк" in low:
        return "донецк", True
    if "москв" in low:
        return "москва", True
    if "питер" in low or "санкт-петербург" in low:
        return "санкт-петербург", True

    clean = re.sub(
        r"(ии|мокси|moxxi|ai|бот|какая|щас|сейчас|сегодня|завтра|узнай|подскажи|скажи|пожалуйста|погода|погоду|погоде|температура|градус|в городе|городе|в|на|у меня|тут|здесь)",
        " ",
        low,
        flags=re.IGNORECASE,
    ).strip()
    clean = re.sub(r"[?!.,;:]", " ", clean).strip()
    words = [w for w in clean.split() if len(w) > 2]
    if words:
        return " ".join(words), False
    return "углегорск", True


async def fetch_weather(lat: float, lon: float, city_name: str) -> dict | None:
    def _req():
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            f"&timezone=auto"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "MoxxiBot/2.1"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    try:
        data = await asyncio.to_thread(_req)
        curr = data.get("current", {})
        temp = curr.get("temperature_2m", 0.0)
        feels = curr.get("apparent_temperature", temp)
        code = curr.get("weather_code", 0)
        humidity = curr.get("relative_humidity_2m", 0)
        wind_kmh = curr.get("wind_speed_10m", 0.0)
        precip = curr.get("precipitation", 0.0)

        wind_ms = round(wind_kmh / 3.6, 1)
        desc = WEATHER_CODES.get(code, "Облачно ⛅️")

        return {
            "city": city_name,
            "temp": temp,
            "feels": feels,
            "desc": desc,
            "humidity": humidity,
            "wind_kmh": wind_kmh,
            "wind_ms": wind_ms,
            "precip": precip,
        }
    except Exception as e:
        print("Weather fetch error:", e)
        return None


async def geocode_city(city_query: str) -> tuple[float, float, str] | None:
    norm = city_query.lower().strip()
    if norm in KNOWN_CITIES:
        return KNOWN_CITIES[norm]

    def _geo():
        url = (
            f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_query)}"
            f"&count=5&language=ru&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "MoxxiBot/2.1"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())

    try:
        data = await asyncio.to_thread(_geo)
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        # if query contains dnr or donetsk, search among results
        if "днр" in norm or "донецк" in norm or "углегорск" in norm:
            for item in results:
                admin1 = str(item.get("admin1", "")).lower()
                if "донецк" in admin1 or "donetsk" in admin1:
                    r = item
                    break
        lat = r["latitude"]
        lon = r["longitude"]
        name = r.get("name", city_query.title())
        adm = r.get("admin1", "")
        country = r.get("country", "")
        display = f"г. {name}"
        if adm:
            display += f" ({adm})"
        elif country:
            display += f" ({country})"
        return (lat, lon, display)
    except Exception as e:
        print("Geocoding error:", e)
        return None


def get_moxxi_weather_tip(temp: float, desc: str) -> str:
    if temp <= 0:
        return "На улице морозно, сладкий! Одевайся теплее или заглядывай ко мне в бар за обжигающим кибер-чаем. ❄️☕️"
    elif temp < 10:
        return "Прохладный денёк! Идеальное время укутаться в куртку и крутить слоты в тепле. 🧥🍸"
    elif temp < 20:
        return "Свежая и бодрящая погода! Самое то для прогулки или битвы с рейдовым боссом. 🌤✨"
    else:
        return "Настоящее киберпанк-лето! Бери освежающий неоновый лимонад и наслаждайся жизнью. 🍹🌴"


async def get_live_weather(query: str) -> str:
    city_str, is_known = extract_city(query)
    geo = await geocode_city(city_str)
    if not geo:
        geo = KNOWN_CITIES["углегорск"]

    lat, lon, display_name = geo
    info = await fetch_weather(lat, lon, display_name)
    if not info:
        return (
            "💋 <b>Мокси:</b>\n"
            "📡 <i>Милый, космические спутники сейчас на калибровке! "
            f"Но в {display_name} точно киберпанк-настроение. Попробуй ещё раз через пару секунд! 🍸</i>"
        )

    t = info["temp"]
    f = info["feels"]
    t_str = f"+{t:.1f}" if t > 0 else f"{t:.1f}"
    f_str = f"+{f:.1f}" if f > 0 else f"{f:.1f}"
    tip = get_moxxi_weather_tip(t, info["desc"])

    return (
        f"💋 <b>Мокси:</b>\n"
        f"🌤 <b>Погода прямо сейчас: {info['city']}</b>\n"
        f"✦ ════════ • ⊰ 🍸 ⛅️ 🌡 👑 ⊱ • ════════ ✦\n\n"
        f"🌡 <b>Температура:</b> <b>{t_str}°C</b> <i>(ощущается как {f_str}°C)</i>\n"
        f"☁️ <b>Состояние:</b> {info['desc']}\n"
        f"💨 <b>Ветер:</b> {info['wind_kmh']} км/ч ({info['wind_ms']} м/с)\n"
        f"💧 <b>Влажность:</b> {info['humidity']}%\n"
        f"🌧 <b>Осадки:</b> {info['precip']} мм\n\n"
        f"🍸 <i>{tip}</i>"
    )


async def main():
    q1 = "ии какая щас погода в донецкой народной республики в городе углегорск"
    ans1 = await get_live_weather(q1)
    print("=== QUERY 1 ===")
    print(ans1.encode("unicode_escape").decode())

    q2 = "какая погода в москве"
    ans2 = await get_live_weather(q2)
    print("=== QUERY 2 ===")
    print(ans2.encode("unicode_escape").decode())

if __name__ == "__main__":
    asyncio.run(main())
