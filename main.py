import os
import requests
import pandas as pd
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

# ====== ПЕРЕМЕННЫЕ ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # твой телеграм id

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY не задан")

# ====== GPT ======
client = OpenAI(api_key=OPENAI_API_KEY)

# ====== TELEGRAM ======
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ====== ЗАГРУЗКА ПРАЙСА ======
try:
    df = pd.read_excel("price.xlsx")
except:
    df = None
    print("⚠️ Прайс не загружен")

# ====== ОПРЕДЕЛЕНИЕ ЯЗЫКА ======
def detect_language(text):
    ua_chars = set("іїєґ")
    if any(c in ua_chars for c in text.lower()):
        return "ua"
    return "ru"

# ====== ПОИСК В ПРАЙСЕ ======
def search_price(query):
    if df is None:
        return None

    results = df[df.iloc[:, 0].astype(str).str.contains(query, case=False, na=False)]

    if results.empty:
        return None

    row = results.iloc[0]

    name = str(row.iloc[0])
    price = str(row.iloc[1])

    return f"{name} — {price} грн"

# ====== GPT ======
def ask_gpt(text):

    lang = detect_language(text)

    if lang == "ua":
        system_prompt = """
Ти менеджер магазину автозапчастин AUTOMAG.

Твоя задача:
- продавати запчастини
- допомагати клієнту
- уточнювати авто
- працювати як живий менеджер

НЕ вигадуй ціни — кажи, що перевіряєш по прайсу.
"""
    else:
        system_prompt = """
Ты менеджер магазина автозапчастей AUTOMAG.

Задача:
- продавать
- уточнять авто
- вести к покупке

НЕ придумывай цены — говори, что проверяешь по прайсу.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Ошибка GPT: {str(e)}"

# ====== ОТПРАВКА ======
def send_message(chat_id, text):
    url = f"{TELEGRAM_URL}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text
    })

# ====== ПРОВЕРКА ЗАКАЗА (ЗАГЛУШКА) ======
def check_order(order_id):
    # тут потом подключим API
    return f"Заказ {order_id}: в обработке"

# ====== WEBHOOK ======
@app.post("/")
async def webhook(request: Request):
    data = await request.json()

    try:
        message = data.get("message")
        if not message:
            return {"ok": True}

        chat_id = message["chat"]["id"]
        text = message.get("text", "").lower()

        # ===== VIN → менеджеру =====
        if "vin" in text or len(text) == 17:
            send_message(chat_id, "Передаю менеджеру 👌")
            if ADMIN_CHAT_ID:
                send_message(ADMIN_CHAT_ID, f"🔥 Клиент отправил VIN:\n{text}")
            return {"ok": True}

        # ===== СТАТУС ЗАКАЗА =====
        if "заказ" in text or "order" in text:
            send_message(chat_id, "Напиши номер заказа 👌")
            return {"ok": True}

        if text.isdigit():
            status = check_order(text)
            send_message(chat_id, status)
            return {"ok": True}

        # ===== ПОИСК ЦЕНЫ =====
        if "цена" in text or "сколько" in text:
            result = search_price(text)
            if result:
                send_message(chat_id, f"Нашёл 👇\n{result}")
            else:
                send_message(chat_id, "Не нашёл, сейчас уточню 👌")
            return {"ok": True}

        # ===== GPT =====
        reply = ask_gpt(text)
        send_message(chat_id, reply)

    except Exception as e:
        print("Ошибка:", e)

    return {"ok": True}
