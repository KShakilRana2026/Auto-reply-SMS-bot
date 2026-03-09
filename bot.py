import telebot
import json
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, GROUP_LINK, CHANNEL_LINK, OWNERS
from telethon.sync import TelegramClient

bot = telebot.TeleBot(BOT_TOKEN)

login_sessions = {}

# ---------- DATABASE ----------
def load_users():
    try:
        with open("database/users.json") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open("database/users.json","w") as f:
        json.dump(data,f,indent=2)

def load_admins():
    try:
        with open("database/admins.json") as f:
            return json.load(f)
    except:
        return {}

def save_admins(data):
    with open("database/admins.json","w") as f:
        json.dump(data,f,indent=2)

# ---------- USER MENU ----------
def user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Add API","🔐 Login Account")
    markup.row("✉️ Set Auto Reply")
    markup.row("▶️ Start Auto Reply","⏹ Stop Auto Reply")
    markup.row("👤 My ID")
    return markup

# ---------- START ----------
@bot.message_handler(commands=['start'])
def start(message):

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("Join Group",url=GROUP_LINK),
        InlineKeyboardButton("Join Channel",url=CHANNEL_LINK)
    )

    markup.add(
        InlineKeyboardButton("Verify",callback_data="verify_join")
    )

    text = """
স্বাগতম Auto Reply Bot এ।

বট ব্যবহার করার আগে আমাদের গ্রুপ এবং চ্যানেলে যোগ দিন।

তারপর VERIFY চাপুন।
"""

    bot.send_message(message.chat.id,text,reply_markup=markup)

# ---------- VERIFY ----------
@bot.callback_query_handler(func=lambda call: call.data=="verify_join")
def verify(call):

    bot.send_message(
        call.message.chat.id,
        "Verification successful.",
        reply_markup=user_menu()
    )

# ---------- ADD API ----------
@bot.message_handler(func=lambda m: m.text=="➕ Add API")
def add_api(message):

    text = """
STEP 1

Open this website:
https://my.telegram.org

Login using your Telegram number.

Go to API Development Tools.

Create an application.

Then send your API ID.
"""

    msg = bot.send_message(message.chat.id,text)

    bot.register_next_step_handler(msg,save_api)

def save_api(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid not in users:
        users[uid] = {}

    users[uid]["api_id"] = message.text

    save_users(users)

    msg = bot.send_message(message.chat.id,"Now send your API HASH")

    bot.register_next_step_handler(msg,save_hash)

def save_hash(message):

    users = load_users()

    uid = str(message.from_user.id)

    users[uid]["api_hash"] = message.text

    save_users(users)

    bot.send_message(message.chat.id,"API saved successfully",reply_markup=user_menu())

# ---------- LOGIN ----------
@bot.message_handler(func=lambda m: m.text=="🔐 Login Account")
def login_account(message):

    bot.send_message(message.chat.id,"Send your phone number\nExample:\n+8801XXXXXXXXX")

    bot.register_next_step_handler(message,phone_login)

def phone_login(message):

    phone = message.text
    uid = str(message.from_user.id)

    users = load_users()

    if uid not in users:
        bot.send_message(message.chat.id,"Please add API first.")
        return

    api_id = int(users[uid]["api_id"])
    api_hash = users[uid]["api_hash"]

    client = TelegramClient(f"sessions/{uid}", api_id, api_hash)

    client.connect()

    client.send_code_request(phone)

    login_sessions[uid] = {
        "client": client,
        "phone": phone
    }

    bot.send_message(message.chat.id,"Login code sent to your Telegram app.\nSend the code here.")

    bot.register_next_step_handler(message,code_login)

def code_login(message):

    uid = str(message.from_user.id)

    code = message.text

    client = login_sessions[uid]["client"]
    phone = login_sessions[uid]["phone"]

    try:

        client.sign_in(phone,code)

        bot.send_message(message.chat.id,"Login successful")

    except Exception as e:

        bot.send_message(message.chat.id,f"Login failed: {e}")

# ---------- SET AUTO REPLY ----------
@bot.message_handler(func=lambda m: m.text=="✉️ Set Auto Reply")
def set_reply(message):

    msg = bot.send_message(message.chat.id,"Write the message people will receive when you are offline.")

    bot.register_next_step_handler(msg,save_reply)

def save_reply(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid not in users:
        users[uid] = {}

    users[uid]["reply"] = message.text

    save_users(users)

    bot.send_message(message.chat.id,"Auto reply message saved",reply_markup=user_menu())

# ---------- START AUTO REPLY ----------
@bot.message_handler(func=lambda m: m.text=="▶️ Start Auto Reply")
def start_reply(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid not in users:
        bot.send_message(message.chat.id,"Add API first.")
        return

    users[uid]["active"] = True

    save_users(users)

    bot.send_message(message.chat.id,"Auto reply started")

# ---------- STOP AUTO REPLY ----------
@bot.message_handler(func=lambda m: m.text=="⏹ Stop Auto Reply")
def stop_reply(message):

    users = load_users()

    uid = str(message.from_user.id)

    if uid in users:
        users[uid]["active"] = False

    save_users(users)

    bot.send_message(message.chat.id,"Auto reply stopped")

# ---------- MY ID ----------
@bot.message_handler(func=lambda m: m.text=="👤 My ID")
def my_id(message):

    bot.send_message(message.chat.id,f"Your ID: {message.from_user.id}")

# ---------- ADMIN ----------
@bot.message_handler(commands=['admin'])
def admin_panel(message):

    admins = load_admins()

    uid = str(message.from_user.id)

    if uid not in admins:
        bot.send_message(message.chat.id,"You are not admin")
        return

    msg = bot.send_message(message.chat.id,"Enter admin password")

    bot.register_next_step_handler(msg,check_admin_password)

def check_admin_password(message):

    admins = load_admins()

    uid = str(message.from_user.id)

    if message.text == admins[uid]["password"]:

        markup = ReplyKeyboardMarkup(resize_keyboard=True)

        markup.row("👥 Total Users")
        markup.row("🚫 Ban User","✅ Unban User")
        markup.row("⬅ Back")

        bot.send_message(message.chat.id,"Admin Panel",reply_markup=markup)

    else:
        bot.send_message(message.chat.id,"Wrong password")

# ---------- OWNER ----------
@bot.message_handler(commands=['owner'])
def owner_panel(message):

    if message.from_user.id not in OWNERS:
        bot.send_message(message.chat.id,"You are not owner")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("➕ Add Admin")
    markup.row("➖ Remove Admin")
    markup.row("📂 User Database")
    markup.row("⬅ Back")

    bot.send_message(message.chat.id,"Owner Panel",reply_markup=markup)

# ---------- BACK ----------
@bot.message_handler(func=lambda m: m.text=="⬅ Back")
def back(message):

    bot.send_message(message.chat.id,"Back to menu",reply_markup=user_menu())

# ---------- RUN ----------
bot.infinity_polling()
