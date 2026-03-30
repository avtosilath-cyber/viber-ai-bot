import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI
user_sessions = {}
app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

URL = f"https://api.telegram.org/bot{TOKEN}"
def get_gpt_response(user_id, user_message):

    if user_id not in user_sessions:
        user_sessions[user_id] = [
            {
                "role": "system",
                "content": "Ты менеджер по автозапчастям. Не спрашивай повторно VIN, если его уже дали. Запоминай данные клиента."
            }
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
    reply = response.choices[0].message.content

    user_sessions[user_id].append({
        "role": "assistant",
        "content": reply
    })

    # ограничение памяти
    if len(user_sessions[user_id]) > 10:
        user_sessions[user_id] = user_sessions[user_id][-10:]

    return reply
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

        # 🔥 GPT ответ
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Ты менеджер магазина автозапчастей. Спрашивай VIN, год, двигатель и помогай подобрать детали."},
                {"role": "user", "content": text}
            ]
        )

        reply = response.choices[0].message.content

        # отправка в Telegram
        requests.post(f"{URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}
