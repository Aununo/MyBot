from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent  

inspire = on_command("启发", priority=5, block=True)

@inspire.handle()
async def handle_inspire(event: MessageEvent):  

    reply_message = """ddb删图事件带给我们的启发:
故事的结局是否重要？
很多人以为的结局是这样一种场景：杂志社的编辑告诉你，还有三个月交稿，多想多看，写坏了没关系，我们时间充裕，重新再写，好好写。
其实不是。
真正的结局是某个下午，你午睡醒来，在纸上潦草地画了几笔，心中想着晚上吃点什么。房门忽然被敲响，来人问你写到了哪。不管上面写了什么，你有多不甘心，多想要修改，这页就是结局。
世事无常，人生不如意太多太多。"""
    
    await inspire.finish(reply_message)