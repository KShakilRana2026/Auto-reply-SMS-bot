import telebot
import json
import os
from telebot.types import ReplyKeyboardMarkup

BOT_TOKEN=os.environ.get("BOT_TOKEN")

bot=telebot.TeleBot(BOT_TOKEN)

def load_users():
    try:
        with open("data/users.json") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open("data/users.json","w") as f:
        json.dump(data,f)

def load_config():
    with open("data/config.json") as f:
        return json.load(f)

def user_menu():
    m=ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("⚙️ Set Reply","📄 My Reply")
    m.add("🟢 Turn ON","🔴 Turn OFF")
    m.add("📊 Dashboard")
    return m

def admin_menu():
    m=ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("👥 Total Users")
    m.add("🔙 Back")
    return m

@bot.message_handler(commands=["start"])
def start(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    if uid not in users:
        users[uid]={
            "reply":"Not set",
            "status":"off",
            "blocked":False
        }
        save_users(users)

    bot.send_message(msg.chat.id,
    "Welcome to Auto SMS System",
    reply_markup=user_menu())

@bot.message_handler(func=lambda m:m.text=="⚙️ Set Reply")
def set_reply(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    if users[uid]["blocked"]:
        bot.send_message(msg.chat.id,"❌ You are blocked")
        return

    bot.send_message(msg.chat.id,"Send your reply message")
    bot.register_next_step_handler(msg,save_reply)

def save_reply(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["reply"]=msg.text
    save_users(users)

    bot.send_message(msg.chat.id,
    "✅ Reply Updated",
    reply_markup=user_menu())

@bot.message_handler(func=lambda m:m.text=="📄 My Reply")
def my_reply(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    bot.send_message(msg.chat.id,
    f"Your Reply:\n\n{users[uid]['reply']}")

@bot.message_handler(func=lambda m:m.text=="🟢 Turn ON")
def on(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["status"]="on"
    save_users(users)

    bot.send_message(msg.chat.id,"✅ Auto Reply ON")

@bot.message_handler(func=lambda m:m.text=="🔴 Turn OFF")
def off(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["status"]="off"
    save_users(users)

    bot.send_message(msg.chat.id,"❌ Auto Reply OFF")

@bot.message_handler(func=lambda m:m.text=="📊 Dashboard")
def dashboard(msg):

    users=load_users()
    uid=str(msg.from_user.id)

    data=users[uid]

    text=f"""
👤 User ID: {uid}

📄 Reply:
{data['reply']}

⚡ Status: {data['status']}
"""

    bot.send_message(msg.chat.id,text)

@bot.message_handler(commands=["admin"])
def admin(msg):

    config=load_config()

    if msg.from_user.id in config["admin"]:
        bot.send_message(msg.chat.id,
        "Admin Panel",
        reply_markup=admin_menu())

@bot.message_handler(func=lambda m:m.text=="👥 Total Users")
def total_users(msg):

    config=load_config()

    if msg.from_user.id not in config["admin"]:
        return

    users=load_users()

    bot.send_message(msg.chat.id,
    f"Total Users: {len(users)}")

@bot.message_handler(commands=["block"])
def block_user(msg):

    config=load_config()

    if msg.from_user.id not in config["admin"]:
        return

    parts=msg.text.split()

    if len(parts)<2:
        bot.reply_to(msg,"Usage: /block USER_ID")
        return

    uid=parts[1]

    users=load_users()

    if uid in users:
        users[uid]["blocked"]=True
        save_users(users)

        bot.reply_to(msg,"User Blocked")

@bot.message_handler(commands=["unblock"])
def unblock_user(msg):

    config=load_config()

    if msg.from_user.id not in config["admin"]:
        return

    parts=msg.text.split()

    if len(parts)<2:
        bot.reply_to(msg,"Usage: /unblock USER_ID")
        return

    uid=parts[1]

    users=load_users()

    if uid in users:
        users[uid]["blocked"]=False
        save_users(users)

        bot.reply_to(msg,"User Unblocked")

@bot.message_handler(commands=["addadmin"])
def add_admin(msg):

    config=load_config()

    if msg.from_user.id not in config["admin"]:
        return

    parts=msg.text.split()

    if len(parts)<2:
        bot.reply_to(msg,"Usage: /addadmin USER_ID")
        return

    new_admin=int(parts[1])

    if new_admin not in config["admin"]:
        config["admin"].append(new_admin)

        with open("data/config.json","w") as f:
            json.dump(config,f)

        bot.reply_to(msg,"New admin added")

@bot.message_handler(commands=["removeadmin"])
def remove_admin(msg):

    config=load_config()

    if msg.from_user.id not in config["admin"]:
        return

    parts=msg.text.split()

    if len(parts)<2:
        bot.reply_to(msg,"Usage: /removeadmin USER_ID")
        return

    admin_id=int(parts[1])

    if admin_id in config["admin"]:
        config["admin"].remove(admin_id)

        with open("data/config.json","w") as f:
            json.dump(config,f)

        bot.reply_to(msg,"Admin removed")

def handler(request):

    if request.method=="POST":
        update=request.json
        bot.process_new_updates([telebot.types.Update.de_json(update)])

    return "ok"
