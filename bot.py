from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update
)
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv
import os
import json

# Завантаження змінних із .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Telegram Token не знайдено. "
        "Переконайтеся, що файл .env існує та містить змінну TELEGRAM_TOKEN=ваш_токен"
    )

# Кроки розмови
ASK_NAME, ASK_LASTNAME, ASK_PHONE, CHOOSE_CAFE, SHOW_MENU_IMAGES, SELECT_MENU, SET_TIME, CONFIRM_ORDER = range(8)

# Адміни
ADMIN_IDS = [443615554]

# База користувачів
USERS_DB = "users.json"
if not os.path.exists(USERS_DB):
    with open(USERS_DB, "w") as f:
        json.dump({}, f)


def is_registered(user_id):
    with open(USERS_DB, "r") as f:
        users = json.load(f)
    return str(user_id) in users


def add_user(user_id, name, last_name, phone):
    with open(USERS_DB, "r") as f:
        users = json.load(f)

    users[str(user_id)] = {
        "name": name,
        "last_name": last_name,
        "phone": phone,
        "last_greet": None
    }

    with open(USERS_DB, "w") as f:
        json.dump(users, f)


# --- Реєстрація ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_registered(user_id):
        await update.message.reply_text("Ви вже зареєстровані! Почнімо замовлення.")
        return await send_cafe_selection(update, context)
    else:
        await update.message.reply_text("Давайте зареєструємо вас! Як вас звати?")
        return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Яке ваше прізвище?")
    return ASK_LASTNAME


async def ask_lastname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_name"] = update.message.text
    button = KeyboardButton("Надати номер телефону", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[button]], one_time_keyboard=True)
    await update.message.reply_text("Надішліть ваш номер телефону:", reply_markup=reply_markup)
    return ASK_PHONE


async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    context.user_data["phone"] = contact.phone_number
    add_user(
        user_id=update.effective_user.id,
        name=context.user_data["name"],
        last_name=context.user_data["last_name"],
        phone=context.user_data["phone"],
    )
    await update.message.reply_text(
        "Дякуємо! Ви успішно зареєструвалися.", reply_markup=ReplyKeyboardRemove()
    )

    async def select_cafe(update: Update, context: ContextTypes.DEFAULT_TYPE):
        selected_cafe = update.message.text
        context.user_data["selected_cafe"] = selected_cafe

        await update.message.reply_text(f"Ви обрали кавʼярню: {selected_cafe}. Зараз покажемо меню.")
        return SHOW_MENU_IMAGES

    # Переходимо до вибору кав'ярні
    return await send_cafe_selection(update, context)

# --- Замовлення ---
async def send_cafe_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = ReplyKeyboardMarkup([["ЖК Львівський", "ЖК Петрівський"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Оберіть кав'ярню для вашого замовлення:",
        reply_markup=reply_markup
    )
    return CHOOSE_CAFE

async def show_menu_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Надсилає зображення меню після вибору кав'ярні."""
    menu_photo_1 = "menu1.jpg"
    menu_photo_2 = "menu2.jpg"

    try:
        # Перше фото
        with open(menu_photo_1, "rb") as photo1:
            await update.message.reply_photo(photo=photo1, caption="Меню")

        # Друге фото
        with open(menu_photo_2, "rb") as photo2:
            await update.message.reply_photo(photo=photo2, caption="Літнє меню")

        # Запит для вибору страви
        await update.message.reply_text("Оберіть будь-що з меню, щоб замовити.")
        return SELECT_MENU

    except FileNotFoundError as e:
        await update.message.reply_text(f"На жаль, не вдалося знайти файл меню: {e}")
    except Exception as e:
        await update.message.reply_text(f"Виникла помилка під час завантаження меню: {e}")



async def select_cafe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_order = context.user_data.setdefault("order", {})
    user_order["cafe"] = update.message.text
    await update.message.reply_text("Напишіть все що хочете замовити:")
    return SELECT_MENU


async def set_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_order = context.user_data["order"]
    user_order["order_details"] = update.message.text
    await update.message.reply_text("На коли замовлення? Напишіть час (наприклад, '15:30') або 'зараз'.")
    return SET_TIME


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_order = context.user_data["order"]
    user_order["time"] = update.message.text

    summary = (
        f"️Перевірте замовлення, та підтвердіть його:\n"
        f"Кав’ярня: {user_order['cafe']}\n"
        f"Замовлення: {user_order['order_details']}\n"
        f"Час: {user_order['time']}\n"
        "Підтвердьте або скасуйте."
    )
    reply_markup = ReplyKeyboardMarkup([["✅Підтвердити", "❌Скасувати"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRM_ORDER


# Підтвердження замовлення
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅Підтвердити":
        user_order = context.user_data["order"]
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                f"Нове замовлення:\n"
                f"Кав’ярня: {user_order['cafe']}\n"
                f"Замовлення: {user_order['order_details']}\n"
                f"Час: {user_order['time']}"
            )
        await update.message.reply_text(
            "Ваше замовлення готується! Дякуємо за ваш вибір! Щоб замовити ще раз, натисніть /start.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Надсилання посилань на групи та Instagram
        await update.message.reply_text(
            "‼️‼️‼️Доєднуйтеся до наших груп у Telegram, щоб бути в курсі всіх новин і пропозицій:\n"
            "👉 [ЖК Львівський](https://t.me/+DDh_eTYqz9FhNzNi)\n"
            "👉 [ЖК Петрівський](https://t.me/zakutoksp)\n\n"
            "Також підписуйтесь на нас в Instagram:\n"
            "📸 [Instagram Закутка](https://www.instagram.com/zakutokkava?igsh=MXZ3NjF0NGp4ejhjNw==)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Замовлення скасовано. Натисніть /start і давай все по новой Міша.", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


# --- Запуск ---
def main():
    app = Application.builder().token(TOKEN).build()

    main_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_LASTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_lastname)],
            ASK_PHONE: [MessageHandler(filters.CONTACT, ask_phone)],
            CHOOSE_CAFE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_cafe)],
            SHOW_MENU_IMAGES: [MessageHandler(filters.TEXT, show_menu_images)],
            SELECT_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_menu)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[],
    )

    app.add_handler(main_handler)
    print("Бот запущений!")
    app.run_polling()


if __name__ == "__main__":
    main()