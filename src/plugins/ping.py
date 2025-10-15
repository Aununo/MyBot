import time
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent


ping = on_command("ping", priority=5, block=True)

@ping.handle()
async def handle_ping(event: MessageEvent):
    sent_time = event.time
    now_time = time.time()
    delay = (now_time - sent_time) * 1000

    reply_message = f"Pong! ⏱️\n延迟: {delay:.2f} ms"
    
    await ping.finish(reply_message)