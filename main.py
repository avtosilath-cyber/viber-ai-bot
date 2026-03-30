import os
import requests
import pandas as pd
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

URL = f"https://api.telegram.org/bot{TOKEN}"

user_sessions = {}

ADMIN_CHAT_ID = 123456789
PRICE_FILE = "price.xlsx"


# 🔎 язык
def detect_language(text):
    ua_chars = set("іїєґ")
    if any(c in ua_chars for c in text.lower()):
        return "ua"
    return "ru"


# 🧠 определяем тип запроса через GPT
def detect_intent(text):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": """Определи тип запроса:

1. article — если есть номер детали (например: A123456, 06A906461)
2. vin — если это VIN код
3. search — если человек просит подбор

Ответь строго одним словом: article / vin / search"""
            },
            {"role": "user", "content": text}
        ]
    )

    return response.choices[0].message.content.strip().lower()


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


# 🤖 GPT диалог
def get_gpt_response(user_id, user_message):

    lang = detect_language(user_message)

    if user_id not in user_sessions:

        system_text = """Ты менеджер магазина автозапчастей AUTOMAG.

Отвечай коротко и по делу.

Всегда сначала уточни:
- есть номер детали?
- или нужен подбор?

Если есть номер — предложи проверить наличие.
Если подбор — запроси VIN.

Не выдумывай запчасти.
Не придумывай цены.
"""

        if lang == "ua":
            system_text += "\nОтвечай только на украинском."
        else:
            system_text += "\nОтвечай только на русском."

        user_sessions[user_id] = [
            {"role": "system", "content": system_text}
        ]

    user_sessions[user_id].append({
        "role": "user",
        "content": user_message
    })

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=user_sessions[user_id]
    )

    reply = response.choices[0].message.content

    user_sessions[user_id].append({
        "role": "assistant",
        "content": reply
    })

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

        # 🔥 номер детали
        if intent == "article":

            parts = search_by_article(text)

            if parts:
                reply = "Ось що знайшов:\n\n" if lang == "ua" else "Вот что нашёл:\n\n"

                for p in parts:
                    reply += f"{p['name']} — {p['price']} грн ({p['stock']})\n"

                reply += "\nЯкий варіант цікавить?" if lang == "ua" else "\nКакой вариант интересует?"

            else:
                reply = "Не знайшов. Напишіть VIN." if lang == "ua" else "Не нашёл. Напишите VIN."

        # 🔥 VIN
        elif intent == "vin":

            reply = "Передаю менеджеру 👍" if lang == "ua" else "Передаю менеджеру 👍"

            requests.post(URL + "/sendMessage", json={
                "chat_id": ADMIN_CHAT_ID,
                "text": f"Заявка VIN:\n{chat_id}\n{text}"
            })

        # 🔥 подбор
        elif intent == "search":

            reply = "Напишіть VIN для підбору" if lang == "ua" else "Напишите VIN для подбора"

        else:
            reply = get_gpt_response(chat_id, text)

        requests.post(URL + "/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}
