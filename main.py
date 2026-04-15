import os
import requests
import pandas as pd
import re
from fastapi import FastAPI, Request
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

users = {}
df = None


# ===== ОТПРАВКА =====
def send(chat_id, text):
  def ask_gpt(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content":
                    "Ты менеджер по продаже автозапчастей AUTOMAG. "
                    "Отвечай на русском и украинском. "
                    "Общайся просто и уверенно. "
                    "Помогай подобрать запчасти и вести к покупке."
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        return "Что-то пошло не так, попробуйте ещё раз 🙌"


# ===== МЕНЕДЖЕР =====
def notify_manager(reason, text, chat_id):
    if not ADMIN_CHAT_ID:
        return

    msg = f"""
🔥 КЛИЕНТ НУЖЕН МЕНЕДЖЕРУ

Причина: {reason}
Сообщение: {text}
ID клиента: {chat_id}

👉 Открыть чат:
https://t.me/{chat_id}
"""
    send(ADMIN_CHAT_ID, msg)


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


# ===== АНАЛОГИ =====
def get_analogs(article):
    if not article:
        return None

    analogs = df[df["article_clean"].str.contains(article[:5], na=False)]

    if analogs.empty:
        return None

    analogs = analogs.sort_values(by="price").head(3)

    return format_results(analogs)


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
        result = format_results(exact)

        analogs = get_analogs(article)
        if analogs:
            result += "\n\n🔁 Аналоги:\n" + analogs

        return result

    contains = df[df["article_clean"].str.contains(article, na=False)]
    if not contains.empty:
        result = format_results(contains)

        analogs = get_analogs(article)
        if analogs:
            result += "\n\n🔁 Аналоги:\n" + analogs

        return result

    fallback = df[df["article_clean"].str.contains(article[:4], na=False)]
    if not fallback.empty:
        result = format_results(fallback)

        analogs = get_analogs(article)
        if analogs:
            result += "\n\n🔁 Аналоги:\n" + analogs

        return result

    return None


# ===== ЗАГРУЗКА ПРАЙСА =====
def load_price():
    try:
        df_raw = pd.read_excel("price.xlsx", header=None)

        header_row = None
        for i in range(15):
            row = df_raw.iloc[i].astype(str).str.lower()
            if row.str.contains("артикул").any():
                header_row = i
                break

        if header_row is None:
            print("❌ Не нашли строку заголовков")
            return None

        df = pd.read_excel("price.xlsx", header=header_row)

        columns = {str(col).lower(): col for col in df.columns}

        def find_col(keys):
            for key in columns:
                for k in keys:
                    if k in key:
                        return columns[key]
            return None

        article_col = find_col(["артикул"])
        name_col = find_col(["название", "наименование"])
        price_col = find_col(["цена"])
        qty_col = find_col(["остаток", "qty"])

        if not article_col:
            print("❌ Нет колонки артикул")
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


# ===== ОСНОВНАЯ ЛОГИКА =====
def handle_message(chat_id, text):
    text_lower = text.lower()

    if chat_id not in users:
        users[chat_id] = {"started": False, "last": ""}

    user = users[chat_id]

    if user["last"] == text:
        return

    user["last"] = text

    # ответы клиента
    if text.strip() in ["1", "да", "Да"]:
        send(chat_id, "🔥 Отлично! Передаю менеджеру для оформления")
        notify_manager("Оформление", text, chat_id)
        return

    if text.strip() == "2":
        send(chat_id, "🔁 Подбираю аналоги...")
        analogs = get_analogs(user.get("last", ""))

        if analogs:
            send(chat_id, analogs)
        else:
            send(chat_id, "Передаю менеджеру для подбора 👌")
            notify_manager("Подбор аналогов", text, chat_id)
        return

    if text.strip() == "3":
        send(chat_id, "Передаю менеджеру 👌")
        notify_manager("Вопрос клиента", text, chat_id)
        return

    if not user["started"]:
        send(chat_id, "Подберу запчасть 🔧 Напишите артикул или название")
        user["started"] = True
        return

    if "vin" in text_lower or len(text.strip()) == 17:
        send(chat_id, "Передаю менеджеру 👌")
        notify_manager("VIN", text, chat_id)
        return

    if "подбор" in text_lower:
        send(chat_id, "Передаю менеджеру 👌")
        notify_manager("Подбор", text, chat_id)
        return

    result = search(text)

    if result:
        send(chat_id, f"""{result}

✅ Есть в наличии
🚚 Быстрая отправка

Оформляем заказ? Напишите:
1️⃣ Да
2️⃣ Нужен аналог
3️⃣ Есть вопрос""")
        return

    send(chat_id, "Не нашли. Передаю менеджеру 👌")
    notify_manager("Не найдено", text, chat_id)


# ===== WEBHOOK =====
@app.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()

        message = data.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")

        text = message.get("text", "")

        if not chat_id:
            return {"ok": True}

        handle_message(chat_id, text)

        return {"ok": True}

    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    handle_message(chat_id, text)
