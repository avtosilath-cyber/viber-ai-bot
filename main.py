import os
import requests
import pandas as pd
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

# ====== ПЕРЕМЕННЫЕ ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY не задан")

# ====== GPT ======
client = OpenAI(api_key=OPENAI_API_KEY)

# ====== TELEGRAM ======
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ====== ПРАЙС ======
try:
    df = pd.read_excel("price.xlsx")
except:
    df = None
    print("⚠️ Прайс не загружен")

# ====== ЯЗЫК ======
def detect_language(text):
    ua_chars = set("іїєґ")
    if any(c in ua_chars for c in text.lower()):
        return "ua"
    return "ru"

# ====== ПОИСК ЦЕНЫ ======
def search_price(query):
    if df is None:
        return None

    results = df[df.iloc[:, 0].astype(str).str.contains(query, case=False, na=False)]

    if results.empty:
        return None

    row = results.iloc[0]

    name = str(row.iloc[0])

    try:
        base_price = float(row.iloc[1])
    except:
        return None

    # 💰 +15% и округление до десятков
    final_price = int(round(base_price * 1.15 / 10) * 10)

    return f"{name} — {final_price} грн"

# ====== GPT ======
def ask_gpt(text):

    lang = detect_language(text)

    if lang == "ua":
        system_prompt = """
Ти менеджер магазину автозапчастин AUTOMAG.

Ти:
- продаєш запчастини
- уточнюєш авто
- ведеш клієнта до покупки

Правила:
- не вигадуй ціни
- якщо питають ціну — скажи що перевіряєш по прайсу
- відповідай коротко і по суті
"""
    else:
        system_prompt = """
Ты менеджер магазина автозапчастей AUTOMAG.

Ты:
- продаёшь запчасти
- уточняешь авто
- ведёшь к покупке

Правила:
- не придумывай цены
- если спрашивают цену — говори, что проверяешь по прайсу
- отвечай кратко
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
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ====== СТАТУС ЗАКАЗА ======
def check_order(order_id):
    return f"Заказ {order_id}: в обработке 👌"

# ====== WEBHOOK ======
@app.post("/")
async def webhook(request: Request):
    data = await request.json()

    try:
        message = data.get("message")
        if not message:
            return {"ok": True}

        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        text_lower = text.lower()

        # ===== VIN → менеджеру =====
        if "vin" in text_lower or len(text) == 17:
            send_message(chat_id, "Передаю менеджеру 👌")
            if ADMIN_CHAT_ID:
                send_message(ADMIN_CHAT_ID, f"🔥 Клиент отправил VIN:\n{text}")
            return {"ok": True}

        # ===== СТАТУС ЗАКАЗА =====
        if "заказ" in text_lower or "order" in text_lower:
            send_message(chat_id, "Напиши номер заказа 👌")
            return {"ok": True}

        if text.isdigit():
            status = check_order(text)
            send_message(chat_id, status)
            return {"ok": True}

        # ===== ПОИСК ЦЕНЫ =====
        if "цена" in text_lower or "сколько" in text_lower:
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
