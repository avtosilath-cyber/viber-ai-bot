import os
import requests
import pandas as pd
import zipfile
import re
from fastapi import FastAPI, Request

app = FastAPI()

# ====== НАСТРОЙКИ ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ====== ФУНКЦИЯ ОЧИСТКИ ======
def clean(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())

# ====== ЗАГРУЗКА ПРАЙСА ======
try:
    with zipfile.ZipFile("merged_min_price.zip") as z:
        file_name = z.namelist()[0]

        with z.open(file_name) as f:
            df = pd.read_excel(f)

    df.columns = df.columns.str.strip().str.lower()

    df["article_clean"] = df["article"].apply(clean)
    df["name_clean"] = df["name"].apply(clean)

    print("✅ Прайс загружен")

except Exception as e:
    df = None
    print("❌ Ошибка:", e)

# ====== ПАМЯТЬ ======
users = {}

# ====== ОТПРАВКА ======
def send(chat_id, text):
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ====== МЕНЕДЖЕР ======
def notify_manager(reason, user_text, chat_id):
    if not ADMIN_CHAT_ID:
        return

    msg = f"""
🔥 КЛИЕНТ НУЖДАЕТСЯ В МЕНЕДЖЕРЕ

Причина: {reason}

Сообщение:
{user_text}

ID:
{chat_id}
"""

    send(ADMIN_CHAT_ID, msg)

# ====== ПОИСК ======
def search(query):
    if df is None:
        return None

    q = clean(query)

    # ищем по совпадению
    results = df[
        df["article_clean"].str.contains(q) |
        df["name_clean"].str.contains(q)
    ]

    # если не нашли — ищем по частям
    if results.empty:
        parts = [p for p in re.split(r"\s+", query.lower()) if len(p) > 2]

        for p in parts:
            p_clean = clean(p)
            temp = df[
                df["article_clean"].str.contains(p_clean) |
                df["name_clean"].str.contains(p_clean)
            ]
            results = pd.concat([results, temp])

    if results.empty:
        return None

    results = results.drop_duplicates().head(3)

    answer = []

    for _, row in results.iterrows():
        try:
            name = str(row["name"])
            price = float(row["price"])
            qty = int(row.get("qty_total", 0))
        except:
            continue

        final_price = int(round(price * 1.15 / 10) * 10)

        if qty > 0:
            answer.append(f"{name} — {final_price} грн (есть: {qty})")
        else:
            answer.append(f"{name} — {final_price} грн (под заказ)")

    return "\n".join(answer)

# ====== ЛОГИКА ======
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

        is_new = chat_id not in users
        users[chat_id] = True

        # ===== ПРИВЕТ =====
        if is_new:
            send(chat_id, "Здравствуйте! Подберу запчасть 👌 Напишите артикул или название.")

        # ===== VIN =====
        if "vin" in text_lower or len(text.strip()) == 17:
            send(chat_id, "Передаю менеджеру 👌")
            notify_manager("VIN", text, chat_id)
            return {"ok": True}

        # ===== ПОДБОР =====
        if "подбери" in text_lower or "подбор" in text_lower:
            send(chat_id, "Передаю менеджеру для подбора 👌")
            notify_manager("Подбор", text, chat_id)
            return {"ok": True}

        # ===== ПОИСК =====
        result = search(text)

        if result:
            send(chat_id, f"Нашёл варианты:\n\n{result}\n\nОформляем?")
            return {"ok": True}

        # ===== НЕ НАШЛИ =====
        send(chat_id, "Не нашли в наличии. Передаю менеджеру 👌")
        notify_manager("Не найдено", text, chat_id)

        return {"ok": True}

    except Exception as e:
        print("❌ Ошибка:", e)

    return {"ok": True}
