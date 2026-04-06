import telebot
import pandas as pd
import re

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
bot = telebot.TeleBot(TOKEN)

# ===== ЗАГРУЗКА ПРАЙСА =====
df = pd.read_excel("prices.xlsx")

df["article_clean"] = df["article"].astype(str).str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
df = df[df["stock"] > 0]


# ===== ПАМЯТЬ ПОЛЬЗОВАТЕЛЕЙ =====
users = {}


def get_user(chat_id):
    if chat_id not in users:
        users[chat_id] = {
            "state": "idle",
            "query": None,
            "article": None,
            "results": [],
            "selected": None,
            "user_type": "retail",
            "phone": None
        }
    return users[chat_id]


# ===== УТИЛИТЫ =====
def extract_article(text):
    text = text.lower()
    words = text.split()

    for w in words:
        clean = re.sub(r'[^a-z0-9]', '', w)
        if any(c.isdigit() for c in clean) and len(clean) >= 5:
            return clean
    return None


def calculate_price(price, user_type):
    if user_type == "vip":
        return round(price * 1.10, 2)
    return round(price * 1.25, 2)


def search_by_article(article):
    return df[df["article_clean"] == article].to_dict("records")


def get_analogs(article):
    return df[df["article_clean"].str.contains(article[:5])].to_dict("records")


def smart_search(text):
    text = text.lower()

    if "масло" in text:
        return df[df["name"].str.contains("oil", case=False, na=False)].to_dict("records")

    if "фильтр" in text:
        return df[df["name"].str.contains("filter", case=False, na=False)].to_dict("records")

    return []


def send_message(chat_id, text, buttons=None):
    if buttons:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for b in buttons:
            markup.add(b)
        bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text)


# ===== ОСНОВНЫЕ ШАГИ =====

def show_best_offer(chat_id, user):
    product = user["results"][0]

    price = calculate_price(product["price"], user["user_type"])

    send_message(chat_id, f"""
🔥 Нашёл лучший вариант:

📦 {product['brand']} {product['article']}
💰 {price} грн
📍 Остаток: {product['stock']}

👇 Что делаем дальше?
""", buttons=[
        "Заказать",
        "Аналоги",
        "Вопрос"
    ])


def request_contact(chat_id):
    send_message(chat_id, "📲 Напиши номер телефона для оформления заказа")


def save_order(user):
    order = {
        "article": user["selected"]["article"],
        "brand": user["selected"]["brand"],
        "price": user["selected"]["price"],
        "phone": user["phone"]
    }

    print("NEW ORDER:", order)


def send_to_manager(chat_id):
    send_message(chat_id, "💬 Передал менеджеру, скоро ответим")


# ===== ОБРАБОТКА СООБЩЕНИЙ =====

@bot.message_handler(func=lambda message: True)
def handle(message):
    chat_id = message.chat.id
    text = message.text

    user = get_user(chat_id)

    # ===== IDLE =====
    if user["state"] == "idle":
        user["query"] = text

        article = extract_article(text)

        if article:
            results = search_by_article(article)
            user["article"] = article
        else:
            results = smart_search(text)

        if results:
            user["results"] = sorted(results, key=lambda x: x["price"])
            user["state"] = "found"
            show_best_offer(chat_id, user)
        else:
            user["state"] = "manager"
            send_to_manager(chat_id)

    # ===== FOUND =====
    elif user["state"] == "found":

        if text == "Заказать":
            user["selected"] = user["results"][0]
            user["state"] = "waiting_contact"
            request_contact(chat_id)

        elif text == "Аналоги":
            user["state"] = "analog"
            analogs = get_analogs(user["article"])

            if analogs:
                user["results"] = sorted(analogs, key=lambda x: x["price"])
                show_best_offer(chat_id, user)
            else:
                send_message(chat_id, "❌ Аналогов нет")

        elif text == "Вопрос":
            user["state"] = "manager"
            send_to_manager(chat_id)

    # ===== WAITING CONTACT =====
    elif user["state"] == "waiting_contact":
        user["phone"] = text
        save_order(user)

        user["state"] = "idle"

        send_message(chat_id, "✅ Заказ принят! Менеджер свяжется с тобой")

    # ===== MANAGER =====
    elif user["state"] == "manager":
        send_to_manager(chat_id)


# ===== ЗАПУСК =====
bot.polling()
