# ================================
# AUTO PARTS BOT — FULL ALGORITHM
# ================================

# ====== CONFIG ======

YES = ["да", "давай", "беру", "оформляем", "подходит", "ок", "окей"]
NO = ["нет", "не надо", "не подходит", "дорого", "отмена"]


# ====== CONTEXT ======

def create_context():
    return {
        "stage": "idle",
        "product": None,
        "last_query": None,
        "order": {
            "city": None,
            "phone": None,
            "delivery": None
        }
    }


# ====== INTENTS ======

def is_yes(text):
    return any(word in text.lower() for word in YES)

def is_no(text):
    return any(word in text.lower() for word in NO)


# ====== MAIN HANDLER ======

def handle_message(user_message, context):

    text = user_message.strip().lower()
    stage = context["stage"]

    # ====== IDLE ======
    if stage == "idle":
        context["stage"] = "search"
        return ask_search()

    # ====== SEARCH ======
    elif stage == "search":

        context["last_query"] = user_message

        product = search_product(user_message)

        if product:
            context["product"] = product
            context["stage"] = "waiting_confirmation"
            return offer_product(product)
        else:
            return not_found()

    # ====== WAITING CONFIRMATION ======
    elif stage == "waiting_confirmation":

        # ❗ КРИТИЧЕСКОЕ МЕСТО — НЕ ДЕЛАТЬ ПОИСК ЗДЕСЬ

        if is_yes(text):
            context["stage"] = "ordering"
            return start_order()

        elif is_no(text):
            context["stage"] = "search"
            context["product"] = None
            return ask_clarify()

        else:
            return repeat_confirmation()

    # ====== ORDERING ======
    elif stage == "ordering":
        return handle_order(user_message, context)

    # ====== DONE ======
    elif stage == "done":
        reset_context(context)
        context["stage"] = "search"
        return "Если ещё что-то нужно — напишите 👍"

    # ====== FALLBACK ======
    else:
        context["stage"] = "search"
        return "Не понял 🤔 Напишите, что нужно подобрать"


# ====== SEARCH FUNCTION ======

def search_product(query):

    # TODO: подключить Excel / API / базу

    # пример:
    return {
        "name": "Тормозные колодки Bosch",
        "price": 1200,
        "stock": "в наличии"
    }

    # если ничего не найдено:
    # return None


# ====== MESSAGES ======

def ask_search():
    return """Напишите:
— марку авто
— модель
— год
— что нужно

Или VIN 👌"""


def offer_product(product):
    return f"""Нашёл 👇

{product['name']}
💰 {product['price']} грн
📦 {product['stock']}

Оформляем? 👌"""


def not_found():
    return """Не нашёл по базе 🤔

Уточните:
— VIN
— точное название детали

Или передам менеджеру 👨‍🔧"""


def repeat_confirmation():
    return "Оформляем или ещё поискать? 👌"


def ask_clarify():
    return "Ок 👍 Давайте подберём другой вариант. Что нужно?"


def start_order():
    return """Супер, оформляем 👍

Напишите:
📍 Город
📞 Телефон
🚚 Доставка (Новая почта / самовывоз)"""


# ====== ORDER FLOW ======

def handle_order(user_message, context):

    order = context["order"]

    # ШАГ 1 — ГОРОД
    if not order["city"]:
        order["city"] = user_message
        return "Введите номер телефона 📞"

    # ШАГ 2 — ТЕЛЕФОН
    elif not order["phone"]:
        order["phone"] = user_message
        return "Способ доставки? Новая почта / самовывоз 🚚"

    # ШАГ 3 — ДОСТАВКА
    elif not order["delivery"]:
        order["delivery"] = user_message

        context["stage"] = "done"

        return confirm_order(context)

    return "Оформляем..."


# ====== CONFIRM ORDER ======

def confirm_order(context):

    product = context["product"]
    order = context["order"]

    return f"""Готово ✅

Товар: {product['name']}
Цена: {product['price']} грн

Город: {order['city']}
Телефон: {order['phone']}
Доставка: {order['delivery']}

Передал менеджеру 👨‍🔧
Скоро свяжутся 👍"""


# ====== RESET ======

def reset_context(context):

    context["product"] = None
    context["last_query"] = None

    context["order"] = {
        "city": None,
        "phone": None,
        "delivery": None
    }
