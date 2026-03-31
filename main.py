import os
import requests
import pandas as pd
import zipfile
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

# ===== ВЫТАСКИВАЕМ АРТИКУЛ =====
def extract_article(text):
    words = text.lower().split()

    for word in words:
        cleaned = clean(word)
        if len(cleaned) >= 3 and any(c.isdigit() for c in cleaned):
            return cleaned

    return None

# ===== ЗАГРУЗКА ПРАЙСА =====
def load_price():
    try:
        with zipfile.ZipFile("merged_min_price.zip") as z:
            file_name = z.namelist()[0]

            with z.open(file_name) as f:
                df = pd.read_excel(f, header=None)

        print("📊 Колонок:", df.shape[1])

        # 🔥 ищем колонку артикула
        article_col = None

        for col in df.columns:
            sample = df[col].astype(str).head(50)
            if sample.str.contains(r"[a-zA-Z]{1,3}\d{2,}", regex=True).any():
                article_col = col
                break

        if article_col is None:
            print("❌ НЕ НАЙДЕНА колонка article")
            return None

        print("✅ article колонка:", article_col)

        df = df.rename(columns={article_col: "article"})

        # цена
        price_col = None
        for col in df.columns:
            if df[col].dtype in ["float64", "int64"]:
                price_col = col
                break

        if price_col:
            df = df.rename(columns={price_col: "price"})
        else:
            df["price"] = 0

        # остаток
        df["qty_total"] = 0

        # имя
        name_col = None
        for col in df.columns:
            if col != "article" and df[col].dtype == object:
                name_col = col
                break

        if name_col:
            df = df.rename(columns={name_col: "name"})
        else:
            df["name"] = ""

        df["article"] = df["article"].astype(str)
        df["name"] = df["name"].astype(str)

        df["article_clean"] = df["article"].apply(clean)

        print("✅ Прайс готов")
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

Сообщение:
{text}

ID:
{chat_id}
"""
    send(ADMIN_CHAT_ID, msg)

# ===== ФОРМАТ =====
def format_results(results):
    results = results.drop_duplicates()

    # сначала в наличии
    in_stock = results[results["qty_total"] > 0]
    if not in_stock.empty:
        results = in_stock

    # сортировка по цене
    results = results.sort_values(by="price")

    results = results.head(3)

    answer = []

    for _, row in results.iterrows():
        try:
            article = row["article"]
            name = row["name"]
            price = float(row["price"])
            qty = int(row.get("qty_total", 0))
        except:
            continue

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

    print("ИЩЕМ:", article)

    if not article:
        return None

    # 1. точное
    exact = df[df["article_clean"] == article]
    if len(exact) > 0:
        return format_results(exact)

    # 2. contains
    contains = df[df["article_clean"].str.contains(article, na=False)]
    if len(contains) > 0:
        return format_results(contains)

    # 3. fallback
    short = article[:4]
    fallback = df[df["article_clean"].str.contains(short, na=False)]

    if len(fallback) > 0:
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

        # память
        if chat_id not in users:
            users[chat_id] = {"started": False, "last": ""}

        user = users[chat_id]

        # не повторяем одно и то же
        if user["last"] == text:
            return {"ok": True}

        user["last"] = text

        # привет 1 раз
        if not user["started"]:
            send(chat_id, "Подберу запчасть 👌 Напишите артикул или название.")
            user["started"] = True
            return {"ok": True}

        # VIN
        if "vin" in text_lower or len(text.strip()) == 17:
            send(chat_id, "Передаю менеджеру 👌")
            notify_manager("VIN", text, chat_id)
            return {"ok": True}

        # подбор
        if "подбор" in text_lower or "подбери" in text_lower:
            send(chat_id, "Передаю менеджеру 👌")
            notify_manager("Подбор", text, chat_id)
            return {"ok": True}

        # поиск
        result = search(text)

        if result:
            send(chat_id, f"{result}\n\nОформляем?")
            return {"ok": True}

        # не нашли
        send(chat_id, "Не нашли. Передаю менеджеру 👌")
        notify_manager("Не найдено", text, chat_id)

        return {"ok": True}

    except Exception as e:
        print("❌ Ошибка:", e)

    return {"ok": True}
