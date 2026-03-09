import telebot
import json
import os
import threading
import asyncio
import re
import time
from telebot.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, GROUP_LINK, CHANNEL_LINK, OWNERS
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

bot = telebot.TeleBot(BOT_TOKEN)

# গ্লোবাল ভেরিয়েবল
active_clients = {}      # চালু থাকা অটো-রিপ্লাই ক্লায়েন্ট
login_sessions = {}      # লগইন প্রক্রিয়ার সময় অস্থায়ী ডাটা

# ---------- ডাটাবেজ ফাংশন ----------
DB_PATH = "database"
USERS_FILE = os.path.join(DB_PATH, "users.json")
ADMINS_FILE = os.path.join(DB_PATH, "admins.json")

def ensure_db():
    if not os.path.exists(DB_PATH):
        os.makedirs(DB_PATH)

def load_users():
    ensure_db()
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(data):
    ensure_db()
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_admins():
    ensure_db()
    try:
        with open(ADMINS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_admins(data):
    ensure_db()
    with open(ADMINS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------- ইউটিলিটি ফাংশন ----------
def is_user_joined_group_channel(user_id):
    """গ্রুপ ও চ্যানেলের সদস্যতা যাচাই (বটকে অ্যাডমিন হতে হবে)"""
    try:
        group_member = bot.get_chat_member(GROUP_LINK, user_id)
        if group_member.status not in ['member', 'administrator', 'creator']:
            return False
        channel_member = bot.get_chat_member(CHANNEL_LINK, user_id)
        if channel_member.status not in ['member', 'administrator', 'creator']:
            return False
        return True
    except Exception:
        return False

def validate_phone(phone):
    return re.match(r'^\+\d{7,15}$', phone) is not None

def validate_api_id(api_id):
    try:
        int(api_id)
        return True
    except ValueError:
        return False

# ---------- ইউজার মেনু ----------
def user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Add API", "🔐 Login Account")
    markup.row("✉️ Set Auto Reply")
    markup.row("▶️ Start Auto Reply", "⏹ Stop Auto Reply")
    markup.row("👤 My ID")
    return markup

# ---------- অ্যাডমিন মেনু ----------
def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👥 Total Users")
    markup.row("🚫 Ban User", "✅ Unban User")
    markup.row("⬅ Back")
    return markup

# ---------- ওনার মেনু ----------
def owner_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Add Admin")
    markup.row("➖ Remove Admin")
    markup.row("📂 User Database")
    markup.row("⬅ Back")
    return markup

# ---------- স্টার্ট কমান্ড ----------
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Join Group", url=GROUP_LINK),
        InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)
    )
    markup.add(
        InlineKeyboardButton("Verify", callback_data="verify_join")
    )

    text = """
স্বাগতম Auto Reply Bot এ।

বট ব্যবহার করার আগে আমাদের গ্রুপ এবং চ্যানেলে যোগ দিন।

তারপর VERIFY চাপুন।
"""
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ---------- ভেরিফাই ----------
@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify(call):
    if is_user_joined_group_channel(call.from_user.id):
        bot.edit_message_text(
            "Verification successful. You can now use the bot.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
        bot.send_message(call.message.chat.id, "Main menu:", reply_markup=user_menu())
    else:
        bot.answer_callback_query(call.id, "You have not joined both group and channel!", show_alert=True)

# ---------- এপিআই যোগ ----------
@bot.message_handler(func=lambda m: m.text == "➕ Add API")
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
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, save_api)

def save_api(message):
    api_id = message.text.strip()
    if not validate_api_id(api_id):
        bot.send_message(message.chat.id, "Invalid API ID. Please enter a numeric ID.")
        return

    users = load_users()
    uid = str(message.from_user.id)
    if uid not in users:
        users[uid] = {}
    users[uid]["api_id"] = api_id
    save_users(users)

    msg = bot.send_message(message.chat.id, "Now send your API HASH")
    bot.register_next_step_handler(msg, save_hash)

def save_hash(message):
    api_hash = message.text.strip()
    if len(api_hash) < 10:
        bot.send_message(message.chat.id, "API hash seems too short. Please check and send again.")
        return

    users = load_users()
    uid = str(message.from_user.id)
    users[uid]["api_hash"] = api_hash
    save_users(users)

    bot.send_message(message.chat.id, "API saved successfully", reply_markup=user_menu())

# ---------- অ্যাকাউন্ট লগইন ----------
@bot.message_handler(func=lambda m: m.text == "🔐 Login Account")
def login_account(message):
    users = load_users()
    uid = str(message.from_user.id)
    if uid not in users or "api_id" not in users[uid] or "api_hash" not in users[uid]:
        bot.send_message(message.chat.id, "Please add API first using '➕ Add API'.")
        return

    bot.send_message(message.chat.id, "Send your phone number with country code.\nExample: +8801XXXXXXXXX")
    bot.register_next_step_handler(message, phone_login)

def phone_login(message):
    phone = message.text.strip()
    if not validate_phone(phone):
        bot.send_message(message.chat.id, "Invalid phone number format. Use international format like +8801XXXXXXXXX.")
        return

    uid = str(message.from_user.id)
    users = load_users()
    api_id = int(users[uid]["api_id"])
    api_hash = users[uid]["api_hash"]

    # অস্থায়ী স্টোরেজে ফোন ও এপিআই রাখি
    login_sessions[uid] = {"phone": phone, "api_id": api_id, "api_hash": api_hash}

    # কোড পাঠানোর জন্য ব্যাকগ্রাউন্ড থ্রেড চালু
    threading.Thread(target=send_code_thread, args=(message.chat.id, uid)).start()

def send_code_thread(chat_id, uid):
    """ব্যাকগ্রাউন্ডে কোড পাঠানোর কাজ"""
    data = login_sessions.get(uid)
    if not data:
        return
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]

    client = TelegramClient(f"sessions/{uid}", api_id, api_hash)

    async def send():
        await client.connect()
        try:
            await client.send_code_request(phone)
            bot.send_message(chat_id, "Verification code sent. Please enter the code.")
            # ক্লায়েন্ট সংযোগ বন্ধ করে দিই, পরে কোড দিয়ে লগইন করব
        except Exception as e:
            bot.send_message(chat_id, f"Error sending code: {e}")
        finally:
            await client.disconnect()

    asyncio.run(send())

# কোড হ্যান্ডলার (যে মেসেজগুলো শুধু ডিজিট এবং ইউজার লগইন সেশনে আছে)
@bot.message_handler(func=lambda m: m.from_user and str(m.from_user.id) in login_sessions and m.text and m.text.isdigit())
def code_login(message):
    uid = str(message.from_user.id)
    code = message.text.strip()
    data = login_sessions.get(uid)
    if not data:
        return

    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    session_file = f"sessions/{uid}"
    client = TelegramClient(session_file, api_id, api_hash)

    async def sign_in():
        await client.connect()
        try:
            await client.sign_in(phone, code)
            bot.send_message(message.chat.id, "Login successful!")
            # সেশন ফাইল সেভ হবে
        except SessionPasswordNeededError:
            bot.send_message(message.chat.id, "Two-step verification enabled. Please send your password.")
            login_sessions[uid]["stage"] = "password"
            login_sessions[uid]["client"] = client  # ক্লায়েন্ট ধরে রাখি
            return
        except Exception as e:
            bot.send_message(message.chat.id, f"Login failed: {e}")
            await client.disconnect()
            del login_sessions[uid]
            return
        await client.disconnect()
        del login_sessions[uid]

    asyncio.run(sign_in())

# পাসওয়ার্ড হ্যান্ডলার
@bot.message_handler(func=lambda m: m.from_user and str(m.from_user.id) in login_sessions and login_sessions[str(m.from_user.id)].get("stage") == "password")
def password_login(message):
    uid = str(message.from_user.id)
    password = message.text
    data = login_sessions[uid]
    client = data["client"]

    async def sign_in_password():
        await client.connect()
        try:
            await client.sign_in(password=password)
            bot.send_message(message.chat.id, "Login successful!")
        except Exception as e:
            bot.send_message(message.chat.id, f"Login failed: {e}")
        finally:
            await client.disconnect()
            del login_sessions[uid]

    asyncio.run(sign_in_password())

# ---------- অটো রিপ্লাই সেট ----------
@bot.message_handler(func=lambda m: m.text == "✉️ Set Auto Reply")
def set_reply(message):
    msg = bot.send_message(message.chat.id, "Write the message people will receive when you are offline.")
    bot.register_next_step_handler(msg, save_reply)

def save_reply(message):
    users = load_users()
    uid = str(message.from_user.id)
    if uid not in users:
        users[uid] = {}
    users[uid]["reply"] = message.text
    save_users(users)
    bot.send_message(message.chat.id, "Auto reply message saved", reply_markup=user_menu())

# ---------- অটো রিপ্লাই চালু ----------
@bot.message_handler(func=lambda m: m.text == "▶️ Start Auto Reply")
def start_reply(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid not in users or "api_id" not in users[uid] or "api_hash" not in users[uid]:
        bot.send_message(message.chat.id, "Please add API first.")
        return
    if "reply" not in users[uid]:
        bot.send_message(message.chat.id, "Please set an auto reply message first.")
        return
    if uid in active_clients:
        bot.send_message(message.chat.id, "Auto reply already running.")
        return

    users[uid]["active"] = True
    save_users(users)

    api_id = int(users[uid]["api_id"])
    api_hash = users[uid]["api_hash"]
    reply_text = users[uid]["reply"]
    session_file = f"sessions/{uid}"
    client = TelegramClient(session_file, api_id, api_hash)

    thread = threading.Thread(target=run_auto_reply, args=(uid, client, reply_text), daemon=True)
    thread.start()
    active_clients[uid] = {"thread": thread, "client": client}
    bot.send_message(message.chat.id, "Auto reply started.")

def run_auto_reply(uid, client, reply_text):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def setup():
        await client.connect()
        if not await client.is_user_authorized():
            bot.send_message(int(uid), "Your session expired. Please login again.")
            if uid in active_clients:
                del active_clients[uid]
            await client.disconnect()
            return

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if event.is_private and not event.message.out and not event.sender.bot:
                users = load_users()
                if uid in users and users[uid].get("active", False):
                    await event.reply(reply_text)

        await client.run_until_disconnected()

    try:
        loop.run_until_complete(setup())
    except Exception as e:
        print(f"Auto-reply error for {uid}: {e}")
    finally:
        loop.close()
        if uid in active_clients:
            del active_clients[uid]
        users = load_users()
        if uid in users:
            users[uid]["active"] = False
            save_users(users)

# ---------- অটো রিপ্লাই বন্ধ ----------
@bot.message_handler(func=lambda m: m.text == "⏹ Stop Auto Reply")
def stop_reply(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid in users:
        users[uid]["active"] = False
        save_users(users)

    if uid in active_clients:
        client = active_clients[uid]["client"]
        if client.loop:
            asyncio.run_coroutine_threadsafe(client.disconnect(), client.loop)
        del active_clients[uid]
        bot.send_message(message.chat.id, "Auto reply stopped.")
    else:
        bot.send_message(message.chat.id, "Auto reply is not running.")

# ---------- আইডি দেখুন ----------
@bot.message_handler(func=lambda m: m.text == "👤 My ID")
def my_id(message):
    bot.send_message(message.chat.id, f"Your ID: {message.from_user.id}")

# ---------- ব্যাক বাটন ----------
@bot.message_handler(func=lambda m: m.text == "⬅ Back")
def back(message):
    bot.send_message(message.chat.id, "Main menu:", reply_markup=user_menu())

# ---------- অ্যাডমিন প্যানেল ----------
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    admins = load_admins()
    uid = str(message.from_user.id)
    if uid not in admins:
        bot.send_message(message.chat.id, "You are not admin.")
        return
    msg = bot.send_message(message.chat.id, "Enter admin password:")
    bot.register_next_step_handler(msg, check_admin_password)

def check_admin_password(message):
    admins = load_admins()
    uid = str(message.from_user.id)
    if message.text == admins[uid]["password"]:
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Wrong password.")

@bot.message_handler(func=lambda m: m.text == "👥 Total Users")
def admin_total_users(message):
    users = load_users()
    bot.send_message(message.chat.id, f"Total users: {len(users)}")

@bot.message_handler(func=lambda m: m.text == "🚫 Ban User")
def admin_ban_user(message):
    msg = bot.send_message(message.chat.id, "Send user ID to ban:")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    uid = message.text.strip()
    users = load_users()
    if uid in users:
        del users[uid]
        save_users(users)
        bot.send_message(message.chat.id, f"User {uid} banned.")
    else:
        bot.send_message(message.chat.id, "User not found.")

@bot.message_handler(func=lambda m: m.text == "✅ Unban User")
def admin_unban_user(message):
    bot.send_message(message.chat.id, "Unban feature not implemented (no ban list).")

# ---------- ওনার প্যানেল ----------
@bot.message_handler(commands=['owner'])
def owner_panel(message):
    if message.from_user.id not in OWNERS:
        bot.send_message(message.chat.id, "You are not owner.")
        return
    bot.send_message(message.chat.id, "Owner Panel", reply_markup=owner_menu())

@bot.message_handler(func=lambda m: m.text == "➕ Add Admin")
def owner_add_admin(message):
    msg = bot.send_message(message.chat.id, "Send user ID and password separated by space.\nExample: `12345678 mypassword`", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Invalid format. Use: <user_id> <password>")
        return
    user_id, password = parts
    admins = load_admins()
    admins[user_id] = {"password": password}
    save_admins(admins)
    bot.send_message(message.chat.id, f"Admin {user_id} added.")

@bot.message_handler(func=lambda m: m.text == "➖ Remove Admin")
def owner_remove_admin(message):
    msg = bot.send_message(message.chat.id, "Send user ID to remove from admin:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    user_id = message.text.strip()
    admins = load_admins()
    if user_id in admins:
        del admins[user_id]
        save_admins(admins)
        bot.send_message(message.chat.id, f"Admin {user_id} removed.")
    else:
        bot.send_message(message.chat.id, "Admin not found.")

@bot.message_handler(func=lambda m: m.text == "📂 User Database")
def owner_user_database(message):
    users = load_users()
    summary = f"Total users: {len(users)}\n\n"
    for uid, data in users.items():
        summary += f"ID: {uid}\n"
        summary += f"  API set: {'Yes' if 'api_id' in data else 'No'}\n"
        summary += f"  Auto-reply: {data.get('reply', 'Not set')[:30]}...\n"
        summary += f"  Active: {data.get('active', False)}\n\n"
    if len(summary) > 4000:
        with open("users_dump.txt", "w") as f:
            f.write(summary)
        with open("users_dump.txt", "rb") as f:
            bot.send_document(message.chat.id, f)
        os.remove("users_dump.txt")
    else:
        bot.send_message(message.chat.id, summary)

# ---------- বট চালু ----------
if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()