from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

SPECIAL_FLAG_TIME = (17, 20)  # 17:20 (Asia/Shanghai)
FAKE_FLAG = "nailong{This_1s_@_fAke_FLAG_haha_what_time_is_love???}"
REAL_FLAG = "nailong{Aununo_has_fallen_in_love_with_you~}"

cat_cmd = on_command("cat", priority=2, block=True)


@cat_cmd.handle()
async def handle_cat_command(event: MessageEvent, args: Message = CommandArg()):
    plain = args.extract_plain_text().strip().lower()

    if plain != "flag":
        await cat_cmd.finish("目前只能查看 flag 哦，用法：/cat flag")

    event_time = datetime.fromtimestamp(event.time, tz=ZoneInfo("UTC")).astimezone(
        ZoneInfo("Asia/Shanghai")
    )

    if (event_time.hour, event_time.minute) == SPECIAL_FLAG_TIME:
        await cat_cmd.finish(REAL_FLAG)
    else:
        await cat_cmd.finish(FAKE_FLAG)

