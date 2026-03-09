import asyncio
from auto_reply import start_auto_reply

def run_session(user_id, api_id, api_hash, reply):

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(
        start_auto_reply(user_id, api_id, api_hash, reply)
    )
