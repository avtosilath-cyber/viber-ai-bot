import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

# 🔑 ключи
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

URL = f"https://api.telegram.org/bot{TOKEN}"

# 🧠 память диалогов
user_sessions = {}

def get_gpt_response(user_id, user_message):

    # создаём сессию если новая
    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {
                "role": "system",
                "content": ""Ты менеджер магазина автозапчастей AUTOMAG.

Отвечай КОРОТКО и по делу.
Не пиши длинные тексты.

Твоя задача:
1. Быстро собрать данные (VIN, год, двигатель)
2. Не спрашивать одно и то же дважды
3. После получения данных — предложить 2-3 варианта запчастей

Формат ответа:
- короткие сообщения
- без лишнего текста
- как живой продавец

Не пиши списки на 10 пунктов.
Не перегружай клиента.

Цель — продать."."
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

    # ограничение памяти (чтобы не жрало деньги)
    if len(user_sessions[user_id]) > 10:
        user_sessions[user_id] = user_sessions[user_id][-10:]

    return reply


# проверка сервера
@app.get("/")
def home():
    return {"status": "ok"}


# webhook от Telegram
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # получаем ответ GPT
        reply = get_gpt_response(chat_id, text)

        # отправляем ответ в Telegram
        requests.post(URL + "/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}
