import os
import requests
import pandas as pd
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

# 🔑 ключи
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

URL = f"https://api.telegram.org/bot{TOKEN}"

# 🧠 память
user_sessions = {}

# 👨‍💼 ваш Telegram ID
ADMIN_CHAT_ID = 123456789  # ВСТАВЬТЕ СВОЙ ID

# 📂 прайс
PRICE_FILE = "price.xlsx"


# 🌍 язык
def detect_language(text):
    ua_chars = set("іїєґ")
    if any(c in ua_chars for c in text.lower()):
        return "ua"
    return "ru"


# 🧠 intent
def detect_intent(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """Определи тип запроса:
article — номер детали
vin — VIN код
search — подбор

Ответь одним словом."""
                },
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip().lower()
    except:
        return "search"


# 🚗 VIN → авто
def detect_car_by_vin(vin):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Определи марку, модель и год авто по VIN. Коротко."
                },
                {"role": "user", "content": vin}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Не удалось определить авто"


# 🔎 поиск
def search_by_article(article):
    try:
        df = pd.read_excel(PRICE_FILE)

        results = df[df["номер"].astype(str).str.contains(article, case=False, na=False)]

        parts = []
        for _, row in results.head(3).iterrows():
            price = int(row["цена"] * 1.15)

            parts.append({
                "name": row["бренд"],
                "price": price,
                "stock": row["наличие"]
            })

        return parts
    except Exception as e:
        print("Ошибка прайса:", e)
        return []


# 🔘 кнопки
def send_buttons(chat_id, lang):
    if lang == "ua":
        text = "Оберіть варіант:"
        keyboard = {
            "keyboard": [
                [{"text": "🔍 Підбір по VIN"}],
                [{"text": "📦 У мене є номер деталі"}]
            ],
            "resize_keyboard": True
        }
    else:
        text = "Выберите вариант:"
        keyboard = {
            "keyboard": [
                [{"text": "🔍 Подбор по VIN"}],
                [{"text": "📦 У меня есть номер детали"}]
            ],
            "resize_keyboard": True
        }

    requests.post(URL + "/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": keyboard
    })


# 🤖 GPT fallback
def get_gpt_response(user_id, user_message):

    lang = detect_language(user_message)

    if user_id not in user_sessions:

        system_text = """Ты менеджер магазина автозапчастей AUTOMAG.

Отвечай коротко.
Сначала выясни:
- номер детали или подбор

Не выдумывай данные.
"""

        if lang == "ua":
            system_text += "\nВідповідай українською."
        else:
            system_text += "\nОтвечай на русском."

        user_sessions[user_id] = [{"role": "system", "content": system_text}]

    user_sessions[user_id].append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=user_sessions[user_id]
    )

    reply = response.choices[0].message.content

    user_sessions[user_id].append({"role": "assistant", "content": reply})

    if len(user_sessions[user_id]) > 10:
        user_sessions[user_id] = user_sessions[user_id][-10:]

    return reply


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        lang = detect_language(text)
        intent = detect_intent(text)
        text_lower = text.lower()

        # 🚀 старт
        if text == "/start":
            send_buttons(chat_id, lang)
            return {"ok": True}

        # 🔘 кнопка VIN
        if "vin" in text_lower:
            reply = "Напишите VIN код" if lang == "ru" else "Напишіть VIN код"

        # 🔘 кнопка номер
        elif "номер" in text_lower:
            reply = "Напишите номер детали" if lang == "ru" else "Напишіть номер деталі"

        # 🔥 VIN
        elif intent == "vin":
            car = detect_car_by_vin(text)

            reply = f"{car}\nПередаю менеджеру 👍" if lang == "ru" else f"{car}\nПередаю менеджеру 👍"

            requests.post(URL + "/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"Заявка VIN\nКлиент: {chat_id}\n{text}\n{car}"
            })

        # 🔥 номер детали
        elif intent == "article":
            parts = search_by_article(text)

            if parts:
                reply = "Вот варианты:\n\n" if lang == "ru" else "Ось варіанти:\n\n"
                for p in parts:
                    reply += f"{p['name']} — {p['price']} грн ({p['stock']})\n"
            else:
                reply = "Не нашёл, напишите VIN" if lang == "ru" else "Не знайшов, напишіть VIN"

        # 🔥 подбор
        elif intent == "search":
            reply = "Напишите VIN для подбора" if lang == "ru" else "Напишіть VIN для підбору"

        # 🤖 fallback
        else:
            reply = get_gpt_response(chat_id, text)

        requests.post(URL + "/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}
