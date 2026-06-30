from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp


@register("hello_astr", "tester", "示例 AstrBot 插件", "1.0.0")
class Hello(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.count = 0

    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        yield event.plain_result(f"你好, {event.get_sender_name() or event.get_sender_id()}!")

    @filter.command("add")
    async def add(self, event: AstrMessageEvent, a: int, b: int):
        yield event.plain_result(f"{a}+{b}={a+b}")

    @filter.command("echo")
    async def echo(self, event: AstrMessageEvent, text: str):
        chain = [Comp.At(qq=event.get_sender_id()), Comp.Plain(" " + text)]
        yield event.chain_result(chain)

    @filter.regex(r"^喵+$")
    async def meow(self, event: AstrMessageEvent):
        yield event.plain_result("喵喵喵~")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all(self, event: AstrMessageEvent):
        self.count += 1
