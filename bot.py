import telebot
import time

BOT_TOKEN = "YOUR_TOKEN"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg,"Bot Working!")

print("Bot Running")

bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
