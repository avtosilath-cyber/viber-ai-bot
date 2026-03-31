import os
import requests
import pandas as pd
import zipfile
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

client = OpenAI(api_key=OPENAI_API_KEY)
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ====== ЗАГРУЗКА ПРАЙСА ИЗ ZIP ======
try:
    with zipfile.ZipFile("merged_min_price.zip") as z:
        file_name = z.namelist()[0]  # берём первый файл внутри

        with z.open(file_name) as f:
            df = pd.read_excel(f)

    df.columns = df.columns.str.strip().str.lower()

    print("✅ Прайс загружен")

except Exception as e:
    df = None
    print("❌ Ошибка загрузки прайса:", e)

# ====== ПАМЯТЬ ======
users = {}

# ====== ЯЗЫК ======
def detect_language(text):
    ua_chars = set("іїєґ")
    if any(c in ua_chars for c in text.lower()):
        return "ua"
    return "ru"

# ====== ПОИСК ======
def search_price(query):
    if df is None:
        return None

    query = query.lower().strip()

    # поиск по артикулу
    article_match = df[df["article"].astype(str).str.lower() == query]

    if not article_match.empty:
        row = article_match.iloc[0]
    else:
        # поиск по названию
        name_match = df[df["name"].astype(str).str.lower().str.contains(query)]

        if name_match.empty:
            return None

        row = name_match.iloc[0]

    try:
        name = str(row["name"])
        base_price = float(row["price"])
        qty = int(row.get("qty_total", 0))
    except:
        return None

    # наценка + округление
    final_price = int(round(base_price * 1.15 / 10) * 10)

    if qty > 0:
        return f"{name} — {final_price} грн\nВ наличии: {qty} шт"
    else:
        return f"{name} — {final_price} грн\nПод заказ 👌"

# ====== GPT ======
def ask_gpt(text, is_new_user):

    lang = detect_language(text)

    greeting = ""
    if is_new_user:
        greeting = "Поздоровайся с клиентом.\n"

    if lang == "ua":
        system_prompt = f"""
Ти менеджер магазину автозапчастин AUTOMAG.

{greeting}

Правила:
- не вигадуй ціни
- не здоровайся кожен раз
- відповідай коротко
"""
    else:
        system_prompt = f"""
Ты менеджер магазина автозапчастей AUTOMAG.

{greeting}

Правила:
- не придумывай цены
- не здоровайся каждый раз
- отвечай кратко
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )

    return response.choices[0].message.content

# ====== ОТПРАВКА ======
def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

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

        # память
        is_new_user = chat_id not in users
        users[chat_id] = True

        # ===== VIN =====
        if "vin" in text_lower or len(text.strip()) == 17:
            send_message(chat_id, "Передаю менеджеру 👌")
            if ADMIN_CHAT_ID:
                send_message(ADMIN_CHAT_ID, f"🔥 VIN клиент:\n{text}")
            return {"ok": True}

        # ===== ПОИСК =====
        result = search_price(text)
        if result:
            send_message(chat_id, result)
            return {"ok": True}

        # ===== GPT =====
        reply = ask_gpt(text, is_new_user)
        send_message(chat_id, reply)

    except Exception as e:
        print("❌ Ошибка:", e)

    return {"ok": True}
