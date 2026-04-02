import os
import requests
import pandas as pd
import re
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

users = {}

# ===== ЧИСТКА =====
def clean(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]", "", text)
    return text

# ===== ИЗВЛЕЧЕНИЕ АРТИКУЛА =====
def extract_article(text):
    words = text.lower().split()
    for word in words:
        cleaned = clean(word)
        if len(cleaned) >= 3 and any(c.isdigit() for c in cleaned):
            return cleaned
    return None

# ===== ЗАГРУЗКА ПРАЙСА (УМНАЯ) =====
def load_price():
    try:
        df_raw = pd.read_excel("price.xlsx", header=None)

        print("📊 RAW:")
        print(df_raw.head(10))

        # 🔥 ищем строку заголовков
        header_row = None
        for i in range(15):
            row = df_raw.iloc[i].astype(str).str.lower()
            if row.str.contains("артикул").any():
                header_row = i
                break

        if header_row is None:
            print("❌ Не нашли строку заголовков")
            return None

        print("✅ Заголовки строка:", header_row)

        # читаем нормально
        df = pd.read_excel("price.xlsx", header=header_row)

        print("📊 Колонки:", df.columns.tolist())

        # 🔥 нормализация названий колонок
        columns = {str(col).lower(): col for col in df.columns}

        def find_col(keys):
            for key in columns:
                for k in keys:
                    if k in key:
                        return columns[key]
            return None

        article_col = find_col(["артикул", "article"])
        name_col = find_col(["наймен", "name"])
        price_col = find_col(["ціна", "price"])
        qty_col = find_col(["кільк", "qty"])

        if not article_col:
            print("❌ Нет article колонки")
            return None

        df = df.rename(columns={
            article_col: "article",
            name_col: "name" if name_col else None,
            price_col: "price" if price_col else None,
            qty_col: "qty_total" if qty_col else None
        })

        df = df.dropna(subset=["article"])

        df["article"] = df["article"].astype(str)
        df["name"] = df.get("name", "").astype(str)
        df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0)
        df["qty_total"] = pd.to_numeric(df.get("qty_total", 0), errors="coerce").fillna(0)

        df["article_clean"] = df["article"].apply(clean)

        print("✅ Прайс загружен:", len(df))

        return df

    except Exception as e:
        print("❌ Ошибка:", e)
        return None


df = load_price()

# ===== ОТПРАВКА =====
def send(chat_id, text):
    requests.post(f"{TELEGRAM_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ===== МЕНЕДЖЕР =====
def notify_manager(reason, text, chat_id):
    if not ADMIN_CHAT_ID:
        return

    msg = f"""
🔥 КЛИЕНТ НУЖЕН МЕНЕДЖЕРУ

Причина: {reason}
Сообщение: {text}
ID: {chat_id}
"""
    send(ADMIN_CHAT_ID, msg)

# ===== ФОРМАТ =====
def format_results(results):
    results = results.drop_duplicates()

    in_stock = results[results["qty_total"] > 0]
    if not in_stock.empty:
        results = in_stock

    results = results.sort_values(by="price").head(3)

    answer = []

    for _, row in results.iterrows():
        article = row["article"]
        name = row["name"]
        price = float(row["price"])
        qty = int(row["qty_total"])

        final_price = int(round(price * 1.15 / 10) * 10)

        if qty > 0:
            answer.append(f"{article} | {name} — {final_price} грн (в наличии: {qty})")
        else:
            answer.append(f"{article} | {name} — {final_price} грн")

    return "\n".join(answer)

# ===== ПОИСК =====
def search(text):
    if df is None:
        return None

    article = extract_article(text)

    print("🔎 ИЩЕМ:", article)

    if not article:
        return None

    exact = df[df["article_clean"] == article]
    if not exact.empty:
        return format_results(exact)

    contains = df[df["article_clean"].str.contains(article, na=False)]
    if not contains.empty:
        return format_results(contains)

    fallback = df[df["article_clean"].str.contains(article[:4], na=False)]
    if not fallback.empty:
        return format_results(fallback)

    return None

# ===== WEBHOOK =====
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

        if chat_id not in users:
            users[chat_id] = {"started": False, "last": ""}

        user = users[chat_id]

        if user["last"] == text:
            return {"ok": True}

        user["last"] = text

        if not user["started"]:
            send(chat_id, "Подберу запчасть 👌 Напишите артикул или название.")
            user["started"] = True
            return {"ok": True}

        if "vin" in text_lower or len(text.strip()) == 17:
            send(chat_id, "Передаю менеджеру 👌")
            notify_manager("VIN", text, chat_id)
            return {"ok": True}

        if "подбор" in text_lower:
            send(chat_id, "Передаю менеджеру 👌")
            notify_manager("Подбор", text, chat_id)
            return {"ok": True}

        result = search(text)

        if result:
            send(chat_id, f"{result}\n\nОформляем?")
            return {"ok": True}

        send(chat_id, "Не нашли. Передаю менеджеру 👌")
        notify_manager("Не найдено", text, chat_id)

        return {"ok": True}

    except Exception as e:
        print("❌ Ошибка:", e)

    return {"ok": True}
