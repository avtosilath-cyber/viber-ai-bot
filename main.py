import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

# ключи
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

URL = f"https://api.telegram.org/bot{TOKEN}"

# память диалогов
user_sessions = {}

def get_gpt_response(user_id, user_message):

    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {
                "role": "system",
                "content": """Ты менеджер магазина автозапчастей AUTOMAG.

Отвечай коротко и по делу, как живой продавец.
Не пиши длинные тексты.

Твоя задача:
1. Быстро собрать данные (VIN, год, двигатель, какая деталь нужна)
2. Не спрашивать одно и то же дважды
3. После получения данных — сразу предлагать варианты

Если клиент дал VIN — НЕ СПРАШИВАЙ его повторно.

Когда понятно, какая деталь нужна — ОБЯЗАТЕЛЬНО предлагай варианты.

Формат ответа:

Варианты:
1. Оригинал — ~2800 грн
2. Аналог (Bosch) — ~1800 грн
3. Бюджет — ~1200 грн

После этого обязательно спроси:
"Какой вариант вас интересует?"

Правила:
- пиши коротко
- не перегружай текстом
- не делай длинных списков
- говори уверенно, как продавец
- цель — помочь выбрать и продать
"""
            }
        ]

    # добавляем сообщение пользователя
    user_sessions[user_id].append({
        "role": "user",
        "content": user_message
    })

    # запрос к GPT
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=user_sessions[user_id]
    )

    reply = response.choices[0].message.content

    # сохраняем ответ
    user_sessions[user_id].append({
        "role": "assistant",
        "content": reply
    })

    # ограничение памяти
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

        reply = get_gpt_response(chat_id, text)

        requests.post(URL + "/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}
