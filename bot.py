import telebot
import json
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, GROUP_LINK, CHANNEL_LINK
from session_manager import run_session

bot = telebot.TeleBot(BOT_TOKEN)


def load_users():
    with open("database/users.json") as f:
        return json.load(f)

def save_users(data):
    with open("database/users.json","w") as f:
        json.dump(data,f)


def user_menu():

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("➕ Add API","🔐 Login Account")
    markup.row("✉️ Set Auto Reply")
    markup.row("▶️ Start Auto Reply","⏹ Stop Auto Reply")
    markup.row("👤 My ID")

    return markup


@bot.message_handler(commands=['start'])
def start(message):

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("Join Group",url=GROUP_LINK),
        InlineKeyboardButton("Join Channel",url=CHANNEL_LINK)
    )

    markup.add(
        InlineKeyboardButton("Verify",callback_data="verify")
    )

    text = """
Welcome to Auto Reply Bot

Before using this bot you must join our group and channel.

After joining press VERIFY.
"""

    bot.send_message(message.chat.id,text,reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def verify(call):

    bot.send_message(
        call.message.chat.id,
        "Verification successful.",
        reply_markup=user_menu()
    )


@bot.message_handler(func=lambda m: m.text == "➕ Add API")
def add_api(message):

    text = """
STEP 1

Open this website:
https://my.telegram.org

Login using your Telegram number.

Go to API Development Tools.

Create a new app.

Then you will see:

api_id
api_hash

Send your API ID now.
"""

    bot.send_message(message.chat.id,text)


@bot.message_handler(func=lambda m: m.text.isdigit())
def save_api(message):

    users = load_users()

    uid = str(message.from_user.id)

    users[uid] = {"api_id":int(message.text)}

    save_users(users)

    bot.send_message(message.chat.id,"Now send your API HASH")


@bot.message_handler(func=lambda m: len(m.text) > 30)
def save_hash(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid in users:

        users[uid]["api_hash"] = message.text

        save_users(users)

        bot.send_message(message.chat.id,"API saved successfully")


@bot.message_handler(func=lambda m: m.text == "✉️ Set Auto Reply")
def set_reply(message):

    bot.send_message(
        message.chat.id,
        "Send the message people will receive when you are offline."
    )


@bot.message_handler(func=lambda m: m.text.startswith("I"))
def save_reply(message):

    users = load_users()

    uid = str(message.from_user.id)

    users[uid]["reply"] = message.text

    save_users(users)

    bot.send_message(message.chat.id,"Auto reply message saved")


@bot.message_handler(func=lambda m: m.text == "▶️ Start Auto Reply")
def start_reply(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid not in users:
        bot.send_message(message.chat.id,"Add API first")
        return

    run_session(
        uid,
        users[uid]["api_id"],
        users[uid]["api_hash"],
        users[uid]["reply"]
    )

    bot.send_message(message.chat.id,"Auto reply started")


@bot.message_handler(func=lambda m: m.text == "👤 My ID")
def my_id(message):

    bot.send_message(
        message.chat.id,
        f"Your ID: {message.from_user.id}"
    )


bot.infinity_polling()
