from telethon import TelegramClient, events

async def start_auto_reply(user_id, api_id, api_hash, reply_text):

    client = TelegramClient(f"sessions/{user_id}", api_id, api_hash)

    replied_users = set()

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):

        if event.is_private:

            sender = await event.get_sender()

            if sender.bot:
                return

            if sender.id in replied_users:
                return

            await event.reply(reply_text)

            replied_users.add(sender.id)

    await client.start()

    await client.run_until_disconnected()
