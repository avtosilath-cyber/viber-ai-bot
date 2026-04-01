# ================================
# AUTO PARTS BOT — PRO VERSION
# ================================

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# ====== CONFIG ======

YES = ["да", "давай", "беру", "оформляем", "подходит", "ок", "окей", "так"]
NO = ["нет", "не надо", "не подходит", "дорого", "отмена"]

PHONE = "097-199-13-30"

KYIV_ADDRESS = "г. Киев, ул. Гавела 67"
DNIPRO_ADDRESS = "г. Днепр, пр. Поля 131"

# ====== USERS ======

users = {}

def get_context(user_id):
    if user_id not in users:
        users[user_id] = {
            "stage": "idle",
            "product": None,
            "last_query": None,
            "order": {
                "city": None,
                "phone": None,
                "delivery": None
            },
            "language": None,
            "greeted": False
        }
    return users[user_id]


# ====== LANGUAGE ======

def detect_language(text):
    ua_words = ["привіт", "дякую", "потрібно", "є", "так"]
    if any(w in text.lower() for w in ua_words):
        return "ua"
    return "ru"


# ====== INTENTS ======

def is_yes(text):
    return any(word in text.lower() for word in YES)

def is_no(text):
    return any(word in text.lower() for word in NO)


# ====== SEARCH ======

def search_product(query):
    if "колодки" in query.lower():
        return {
            "name": "Тормозные колодки Bosch",
            "price": 1200,
            "stock": "в наличии"
        }
    return None


# ====== TEXTS ======

def greet(lang):
    if lang == "ua":
        return f"""Вітаю 👋

Я підберу запчастини для вашого авто 🚗

Напишіть:
— марку
— модель
— рік
— що потрібно

Або VIN 👌

📞 Для консультації: {PHONE}"""
    else:
        return f"""Здравствуйте 👋

Подберу запчасти для вашего авто 🚗

Напишите:
— марку
— модель
— год
— что нужно

Или VIN 👌

📞 Для консультации: {PHONE}"""


def offer(product, lang):
    if lang == "ua":
        return f"""{product['name']}
💰 {product['price']} грн
📦 {product['stock']}

Оформлюємо?"""
    else:
        return f"""{product['name']}
💰 {product['price']} грн
📦 {product['stock']}

Оформляем?"""


def start_order(lang):
    if lang == "ua":
        return f"""Супер 👍

Напишіть:
📍 Місто
📞 Телефон
🚚 Доставка (Нова пошта / самовивіз)

Самовивіз:
Київ — {KYIV_ADDRESS}
Дніпро — {DNIPRO_ADDRESS}"""
    else:
        return f"""Отлично 👍

Напишите:
📍 Город
📞 Телефон
🚚 Доставка (Новая почта / самовывоз)

Самовывоз:
Киев — {KYIV_ADDRESS}
Днепр — {DNIPRO_ADDRESS}"""


def not_found(lang):
    if lang == "ua":
        return f"""Не знайшов 🤔

Уточніть VIN або деталь

📞 Або телефонуйте: {PHONE}"""
    else:
        return f"""Не нашёл 🤔

Уточните VIN или деталь

📞 Или звоните: {PHONE}"""


def confirm_order(context, lang):
    p = context["product"]
    o = context["order"]

    if lang == "ua":
        return f"""Готово ✅

{p['name']} — {p['price']} грн

Місто: {o['city']}
Телефон: {o['phone']}
Доставка: {o['delivery']}

Менеджер зв'яжеться 👍

📞 {PHONE}"""
    else:
        return f"""Готово ✅

{p['name']} — {p['price']} грн

Город: {o['city']}
Телефон: {o['phone']}
Доставка: {o['delivery']}

Менеджер свяжется 👍

📞 {PHONE}"""


# ====== BOT CORE ======

def handle_message(user_message, context):

    text = user_message.lower()

    # язык
    if not context["language"]:
        context["language"] = detect_language(text)

    lang = context["language"]

    # приветствие 1 раз
    if not context["greeted"]:
        context["greeted"] = True
        context["stage"] = "search"
        return greet(lang)

    stage = context["stage"]

    # ===== SEARCH =====
    if stage == "search":

        product = search_product(user_message)

        if product:
            context["product"] = product
            context["stage"] = "waiting_confirmation"
            return offer(product, lang)
        else:
            return not_found(lang)

    # ===== CONFIRM =====
    elif stage == "waiting_confirmation":

        if is_yes(text):
            context["stage"] = "ordering"
            return start_order(lang)

        elif is_no(text):
            context["stage"] = "search"
            return "Ок, напишите что нужно"

        else:
            return "Оформляем или ещё ищем?"

    # ===== ORDER =====
    elif stage == "ordering":

        order = context["order"]

        if not order["city"]:
            order["city"] = user_message
            return "Телефон 📞"

        elif not order["phone"]:
            order["phone"] = user_message
            return "Доставка? Новая почта / самовывоз"

        elif not order["delivery"]:
            order["delivery"] = user_message
            context["stage"] = "done"
            return confirm_order(context, lang)

    # ===== DONE =====
    elif stage == "done":
        context["stage"] = "search"
        return "Если ещё нужно — пишите 👍"

    return "Напишите, что нужно"
    

# ====== API ======

@app.route("/", methods=["GET"])
def home():
    return "Bot is alive 🚀"


@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    user_id = str(data.get("user_id", "test"))
    message = data.get("message", "")

    context = get_context(user_id)

    reply = handle_message(message, context)

    return jsonify({"reply": reply})


# ====== RUN ======

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=PORT)
