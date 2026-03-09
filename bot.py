import telebot
import json
import os
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.environ.get("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def load_users():
    with open("database/users.json") as f:
        return json.load(f)

def save_users(data):
    with open("database/users.json","w") as f:
        json.dump(data,f)

def load_admins():
    with open("database/admins.json") as f:
        return json.load(f)

def save_admins(data):
    with open("database/admins.json","w") as f:
        json.dump(data,f)

def load_config():
    with open("database/config.json") as f:
        return json.load(f)

CONFIG = load_config()
MAIN_ADMIN = CONFIG["main_admin"]

def user_menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("Set SMS Reply","My Reply")
    m.add("Turn ON","Turn OFF")
    m.add("Dashboard","My ID")
    m.add("Admin Panel")
    return m

def admin_menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("Total Users","Users")
    m.add("Block User","Unblock User")
    m.add("Broadcast","Get Admin ID")
    m.add("Back Menu")
    return m

def main_admin_menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("Add Admin","Remove Admin")
    m.add("Set Admin Password","Main Admin")
    m.add("Back Menu")
    return m

@bot.message_handler(commands=['start'])
def start(msg):

    users = load_users()
    uid = str(msg.from_user.id)

    if uid not in users:
        users[uid] = {
            "reply":"Not set",
            "status":"off",
            "blocked":False
        }
        save_users(users)

    bot.send_message(msg.chat.id,"Welcome to SMS Reply Bot",reply_markup=user_menu())

@bot.message_handler(func=lambda m: m.text=="Set SMS Reply")
def set_reply(msg):
    bot.send_message(msg.chat.id,"Send your reply message")
    bot.register_next_step_handler(msg,save_reply)

def save_reply(msg):
    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["reply"]=msg.text
    save_users(users)

    bot.send_message(msg.chat.id,"Reply saved")

@bot.message_handler(func=lambda m: m.text=="My Reply")
def my_reply(msg):
    users=load_users()
    uid=str(msg.from_user.id)

    bot.send_message(msg.chat.id,users[uid]["reply"])

@bot.message_handler(func=lambda m: m.text=="Turn ON")
def turn_on(msg):
    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["status"]="on"
    save_users(users)

    bot.send_message(msg.chat.id,"Reply system enabled")

@bot.message_handler(func=lambda m: m.text=="Turn OFF")
def turn_off(msg):
    users=load_users()
    uid=str(msg.from_user.id)

    users[uid]["status"]="off"
    save_users(users)

    bot.send_message(msg.chat.id,"Reply system disabled")

@bot.message_handler(func=lambda m: m.text=="Dashboard")
def dashboard(msg):
    users=load_users()
    uid=str(msg.from_user.id)

    data=users[uid]

    text=f"""
User ID: {uid}

Reply: {data['reply']}

Status: {data['status']}
"""

    bot.send_message(msg.chat.id,text)

@bot.message_handler(func=lambda m: m.text=="My ID")
def myid(msg):
    bot.send_message(msg.chat.id,str(msg.from_user.id))

@bot.message_handler(func=lambda m: m.text=="Admin Panel")
def admin_panel(msg):

    uid = msg.from_user.id

    if uid in MAIN_ADMIN:
        bot.send_message(msg.chat.id,"Main Admin Panel",reply_markup=main_admin_menu())
        return

    admins=load_admins()

    if str(uid) in admins:
        bot.send_message(msg.chat.id,"Enter admin password")
        bot.register_next_step_handler(msg,check_password)
    else:
        bot.send_message(msg.chat.id,"You are not admin")

def check_password(msg):

    uid=str(msg.from_user.id)
    admins=load_admins()

    if msg.text==admins[uid]["password"]:
        bot.send_message(msg.chat.id,"Admin Panel",reply_markup=admin_menu())
    else:
        bot.send_message(msg.chat.id,"Wrong password")

@bot.message_handler(func=lambda m: m.text=="Total Users")
def total_users(msg):

    users=load_users()
    bot.send_message(msg.chat.id,f"Total Users: {len(users)}")

@bot.message_handler(func=lambda m: m.text=="Block User")
def block_user(msg):
    bot.send_message(msg.chat.id,"Send user ID")
    bot.register_next_step_handler(msg,do_block)

def do_block(msg):
    uid=msg.text
    users=load_users()

    if uid in users:
        users[uid]["blocked"]=True
        save_users(users)
        bot.send_message(msg.chat.id,"User blocked")

@bot.message_handler(func=lambda m: m.text=="Unblock User")
def unblock_user(msg):
    bot.send_message(msg.chat.id,"Send user ID")
    bot.register_next_step_handler(msg,do_unblock)

def do_unblock(msg):
    uid=msg.text
    users=load_users()

    if uid in users:
        users[uid]["blocked"]=False
        save_users(users)
        bot.send_message(msg.chat.id,"User unblocked")

@bot.message_handler(func=lambda m: m.text=="Broadcast")
def broadcast(msg):
    bot.send_message(msg.chat.id,"Send message")
    bot.register_next_step_handler(msg,send_broadcast)

def send_broadcast(msg):

    users=load_users()

    for u in users:
        try:
            bot.send_message(u,msg.text)
        except:
            pass

    bot.send_message(msg.chat.id,"Broadcast completed")

@app.route('/webhook',methods=['POST'])
def webhook():

    json_str=request.get_data().decode('UTF-8')
    update=telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])

    return "ok"

@app.route('/')
def home():
    return "Bot Running"

if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
