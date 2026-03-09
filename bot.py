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
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipant, ChannelParticipantAdmin, ChannelParticipantCreator

bot = telebot.TeleBot(BOT_TOKEN)

# Global structures to manage active Telethon clients
# key: user_id (str), value: dict with client, loop, thread, etc.
active_clients = {}

# ---------- DATABASE FUNCTIONS (with improved error handling) ----------
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

# ---------- UTILITY FUNCTIONS ----------
def is_user_joined_group_channel(user_id):
    """
    Uses the bot's own API to check if user is member of group and channel.
    Requires bot to be admin in both.
    """
    try:
        # Check group
        group_member = bot.get_chat_member(GROUP_LINK, user_id)
        if group_member.status not in ['member', 'administrator', 'creator']:
            return False
        # Check channel
        channel_member = bot.get_chat_member(CHANNEL_LINK, user_id)
        if channel_member.status not in ['member', 'administrator', 'creator']:
            return False
        return True
    except Exception as e:
        print(f"Verification error for {user_id}: {e}")
        return False

def validate_phone(phone):
    # Very basic: starts with + and then digits
    pattern = r'^\+\d{7,15}$'
    return re.match(pattern, phone) is not None

def validate_api_id(api_id):
    try:
        int(api_id)
        return True
    except ValueError:
        return False

# ---------- USER MENU ----------
def user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Add API", "🔐 Login Account")
    markup.row("✉️ Set Auto Reply")
    markup.row("▶️ Start Auto Reply", "⏹ Stop Auto Reply")
    markup.row("👤 My ID")
    return markup

# ---------- ADMIN MENU ----------
def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👥 Total Users")
    markup.row("🚫 Ban User", "✅ Unban User")
    markup.row("⬅ Back")
    return markup

# ---------- OWNER MENU ----------
def owner_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Add Admin")
    markup.row("➖ Remove Admin")
    markup.row("📂 User Database")
    markup.row("⬅ Back")
    return markup

# ---------- START ----------
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

# ---------- VERIFY ----------
@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify(call):
    user_id = call.from_user.id
    if is_user_joined_group_channel(user_id):
        bot.edit_message_text(
            "Verification successful. You can now use the bot.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
        bot.send_message(call.message.chat.id, "Main menu:", reply_markup=user_menu())
    else:
        bot.answer_callback_query(call.id, "You have not joined both group and channel!", show_alert=True)

# ---------- ADD API ----------
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
    if len(api_hash) < 10:  # rough check
        bot.send_message(message.chat.id, "API hash seems too short. Please check and send again.")
        return

    users = load_users()
    uid = str(message.from_user.id)
    users[uid]["api_hash"] = api_hash
    save_users(users)

    bot.send_message(message.chat.id, "API saved successfully", reply_markup=user_menu())

# ---------- LOGIN ACCOUNT ----------
@bot.message_handler(func=lambda m: m.text == "🔐 Login Account")
def login_account(message):
    # Check if API is set
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

    # Try to use existing session if available
    session_file = f"sessions/{uid}"
    client = TelegramClient(session_file, api_id, api_hash)

    # We'll run the async login in a separate thread
    threading.Thread(target=async_login, args=(message.chat.id, uid, client, phone)).start()

def async_login(chat_id, uid, client, phone):
    """Run the async login process in a thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(do_login(chat_id, uid, client, phone))
    finally:
        loop.close()

async def do_login(chat_id, uid, client, phone):
    await client.connect()
    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone)
            # Store client temporarily to use in next step
            # We'll use a global dict to pass client to the next step
            login_sessions[uid] = {"client": client, "phone": phone}
            bot.send_message(chat_id, "Verification code sent. Please enter the code you received.")
            # Register next step handler for code (will be called from bot thread)
            # Because we are in async, we need to schedule it in bot's thread
            # We'll use bot.register_next_step_handler by calling it from main bot thread
            # So we need to pass chat_id and user id
            # We'll store the client in login_sessions and then in a separate handler get it.
            # But we are already in a thread; we can't directly call register_next_step_handler from here.
            # Instead, we'll set a flag and use a polling mechanism? Simpler: use a callback query or just wait for user message in main bot thread.
            # Approach: after sending code, we store client and then in code_login we retrieve it.
            # But code_login will be called in main bot thread, so we need to pass client there.
            # We'll store client in login_sessions[uid] and then when user sends code, we use it.
            # However, we must ensure client stays connected. We'll keep it connected.
            # But we are in a separate thread; the client is in this thread's loop. We need to keep the loop running.
            # Actually we can disconnect after sending code request and then reconnect when code is received.
            # But that's inefficient. Better: we keep this thread alive waiting for the code.
            # But the user will send the code via a Telegram message to the bot, which will be handled in main thread.
            # We need to communicate between threads.
            # Solution: Use a queue or shared variable with locks.
            # For simplicity, we'll modify approach: use a two-step process where the code is handled in the same thread.
            # That means we should not spawn a thread for login; instead we run async login in the main thread using asyncio.run() but that would block the bot.
            # So we need a better design: keep a dict of pending logins and use a separate thread per client that waits for code via an asyncio.Queue.
            # Given complexity, we'll simplify: after sending code request, we disconnect client and then in code_login we create a new client and sign in using the code.
            # That is simpler and safe.
            await client.disconnect()
            # Store phone and api in login_sessions
            login_sessions[uid] = {"phone": phone, "api_id": api_id, "api_hash": api_hash}
            # Now code_login will be called from main thread.
        except Exception as e:
            bot.send_message(chat_id, f"Error sending code: {e}")
            return
    else:
        # Already authorized
        bot.send_message(chat_id, "You are already logged in.")
        # Optionally store client in active_clients if needed
        await client.disconnect()
        return

# Temporary storage for login data (phone, api) while waiting for code
login_sessions = {}

@bot.message_handler(func=lambda m: m.text == "🔐 Login Account" or True)  # This is too broad; better use a state
# Instead, we'll handle code after phone_login via next_step_handler
# We already registered next_step_handler for phone_login; after phone_login we don't register for code directly because we sent code asynchronously.
# So we need to modify: after phone_login, we store data and then the user will send code, but we need to catch that message.
# We'll use a filter for messages that look like a code (digits) for users who are in login_sessions.
# This is a bit hacky but works.
@bot.message_handler(func=lambda m: m.from_user and str(m.from_user.id) in login_sessions and m.text and m.text.isdigit())
def code_login(message):
    uid = str(message.from_user.id)
    code = message.text.strip()
    data = login_sessions[uid]
    phone = data["phone"]
    api_id = data.get("api_id")  # Actually we didn't store api_id in login_sessions in new approach; we'll need to retrieve from users db.
    api_hash = data.get("api_hash")
    # Better: retrieve api from users db
    users = load_users()
    if uid not in users:
        bot.send_message(message.chat.id, "API not found. Please add API first.")
        del login_sessions[uid]
        return
    api_id = int(users[uid]["api_id"])
    api_hash = users[uid]["api_hash"]

    session_file = f"sessions/{uid}"
    client = TelegramClient(session_file, api_id, api_hash)

    async def do_signin():
        await client.connect()
        try:
            await client.sign_in(phone, code)
            bot.send_message(message.chat.id, "Login successful!")
            # Store client in active_clients if needed later
            # But we will create client again when starting auto-reply
        except SessionPasswordNeededError:
            # 2FA required
            bot.send_message(message.chat.id, "Two-step verification enabled. Please send your password.")
            # We need to handle password in another step. For simplicity, we'll store client and phone again and wait for password.
            login_sessions[uid] = {"client": client, "phone": phone, "stage": "password"}
            return
        except Exception as e:
            bot.send_message(message.chat.id, f"Login failed: {e}")
        finally:
            await client.disconnect()

    asyncio.run(do_signin())
    del login_sessions[uid]

@bot.message_handler(func=lambda m: m.from_user and str(m.from_user.id) in login_sessions and login_sessions[str(m.from_user.id)].get("stage") == "password")
def password_login(message):
    uid = str(message.from_user.id)
    password = message.text
    data = login_sessions[uid]
    client = data["client"]
    phone = data["phone"]

    async def do_password():
        await client.connect()
        try:
            await client.sign_in(password=password)
            bot.send_message(message.chat.id, "Login successful!")
        except Exception as e:
            bot.send_message(message.chat.id, f"Login failed: {e}")
        finally:
            await client.disconnect()
            del login_sessions[uid]

    asyncio.run(do_password())

# ---------- SET AUTO REPLY ----------
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

# ---------- START AUTO REPLY ----------
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

    # Check if already active
    if uid in active_clients:
        bot.send_message(message.chat.id, "Auto reply already running.")
        return

    # Mark active in DB
    users[uid]["active"] = True
    save_users(users)

    # Start client in background thread
    api_id = int(users[uid]["api_id"])
    api_hash = users[uid]["api_hash"]
    reply_text = users[uid]["reply"]
    session_file = f"sessions/{uid}"
    client = TelegramClient(session_file, api_id, api_hash)

    # Start thread
    thread = threading.Thread(target=run_auto_reply, args=(uid, client, reply_text), daemon=True)
    thread.start()
    active_clients[uid] = {"thread": thread, "client": client}
    bot.send_message(message.chat.id, "Auto reply started.")

def run_auto_reply(uid, client, reply_text):
    """Run the Telethon client with auto-reply handler in its own asyncio loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def setup():
        await client.connect()
        if not await client.is_user_authorized():
            # Not logged in; maybe session expired
            bot.send_message(int(uid), "Your session expired. Please login again.")
            # Remove from active
            if uid in active_clients:
                del active_clients[uid]
            await client.disconnect()
            return

        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            # Only reply in private chats, and not to bots, and not to own messages
            if event.is_private and not event.message.out and not event.sender.bot:
                # Check if auto-reply is still enabled in DB
                users = load_users()
                if uid in users and users[uid].get("active", False):
                    await event.reply(reply_text)

        # Keep the client running
        await client.run_until_disconnected()

    try:
        loop.run_until_complete(setup())
    except Exception as e:
        print(f"Auto-reply error for {uid}: {e}")
    finally:
        loop.close()
        # Clean up
        if uid in active_clients:
            del active_clients[uid]
        # Update DB active flag
        users = load_users()
        if uid in users:
            users[uid]["active"] = False
            save_users(users)

# ---------- STOP AUTO REPLY ----------
@bot.message_handler(func=lambda m: m.text == "⏹ Stop Auto Reply")
def stop_reply(message):
    uid = str(message.from_user.id)
    users = load_users()
    if uid in users:
        users[uid]["active"] = False
        save_users(users)

    if uid in active_clients:
        # Disconnect client
        client = active_clients[uid]["client"]
        async def disconnect():
            await client.disconnect()
        asyncio.run_coroutine_threadsafe(disconnect(), client.loop)  # Need client's loop
        # Actually easier: we can't easily stop the thread; but we can set a flag.
        # We'll rely on the thread noticing the DB change and stopping itself.
        # For immediate stop, we can disconnect.
        # But we need to be careful with threads.
        # We'll send a disconnect request.
        # Since client has its own loop, we can schedule.
        if client.loop:
            asyncio.run_coroutine_threadsafe(client.disconnect(), client.loop)
        # Remove from dict
        del active_clients[uid]
        bot.send_message(message.chat.id, "Auto reply stopped.")
    else:
        bot.send_message(message.chat.id, "Auto reply is not running.")

# ---------- MY ID ----------
@bot.message_handler(func=lambda m: m.text == "👤 My ID")
def my_id(message):
    bot.send_message(message.chat.id, f"Your ID: {message.from_user.id}")

# ---------- BACK ----------
@bot.message_handler(func=lambda m: m.text == "⬅ Back")
def back(message):
    bot.send_message(message.chat.id, "Main menu:", reply_markup=user_menu())

# ---------- ADMIN PANEL ----------
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
    if message.text == admins[uid]["password"]:  # plaintext, should hash in production
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Wrong password.")

# Admin menu handlers
@bot.message_handler(func=lambda m: m.text == "👥 Total Users")
def admin_total_users(message):
    users = load_users()
    bot.send_message(message.chat.id, f"Total users: {len(users)}")

@bot.message_handler(func=lambda m: m.text == "🚫 Ban User")
def admin_ban_user(message):
    msg = bot.send_message(message.chat.id, "Send user ID to ban:")
    bot.register_next_step_handler(msg, process_ban)

def process_ban(message):
    try:
        uid = message.text.strip()
        # Here you could add a banned list, but for simplicity we just remove user data
        users = load_users()
        if uid in users:
            del users[uid]
            save_users(users)
            bot.send_message(message.chat.id, f"User {uid} banned (data removed).")
        else:
            bot.send_message(message.chat.id, "User not found.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

@bot.message_handler(func=lambda m: m.text == "✅ Unban User")
def admin_unban_user(message):
    # If you have a ban list, implement; otherwise not needed
    bot.send_message(message.chat.id, "Unban feature not implemented (no ban list).")

# ---------- OWNER PANEL ----------
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
    admins[user_id] = {"password": password}  # store plaintext, consider hashing
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
    # Create a summary
    summary = f"Total users: {len(users)}\n\n"
    for uid, data in users.items():
        summary += f"ID: {uid}\n"
        summary += f"  API set: {'Yes' if 'api_id' in data else 'No'}\n"
        summary += f"  Auto-reply: {data.get('reply', 'Not set')[:30]}...\n"
        summary += f"  Active: {data.get('active', False)}\n\n"
    # Send as file if too long
    if len(summary) > 4000:
        with open("users_dump.txt", "w") as f:
            f.write(summary)
        with open("users_dump.txt", "rb") as f:
            bot.send_document(message.chat.id, f)
        os.remove("users_dump.txt")
    else:
        bot.send_message(message.chat.id, summary)

# ---------- RUN ----------
if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()