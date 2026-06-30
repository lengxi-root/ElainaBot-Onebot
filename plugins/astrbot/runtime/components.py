"""AstrBot 消息组件 + MessageChain (适配 OneBot v11)。

每个组件实现 ``to_segment()`` 把自身转成 OneBot v11 消息段 (dict)，
以及保留 AstrBot 上游常用的属性/方法名，确保插件无感运行。
"""

from __future__ import annotations

import base64
import os


class ComponentType:
    Plain = "Plain"
    Face = "Face"
    Image = "Image"
    At = "At"
    AtAll = "AtAll"
    Record = "Record"
    Video = "Video"
    File = "File"
    Reply = "Reply"
    Node = "Node"
    Nodes = "Nodes"
    Poke = "Poke"
    Forward = "Forward"
    Json = "Json"
    Unknown = "Unknown"


class BaseMessageComponent:
    type: str = "Unknown"

    def toDict(self) -> dict:  # noqa: N802 (与上游同名)
        return {"type": self.type.lower(), "data": {}}

    def to_segment(self) -> dict | None:
        return self.toDict()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"


class Plain(BaseMessageComponent):
    type = "Plain"

    def __init__(self, text: str = "", convert: bool = True, **_):
        self.text = str(text) if text is not None else ""
        self.convert = convert

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "text", "data": {"text": self.text}}


class Face(BaseMessageComponent):
    type = "Face"

    def __init__(self, id=None, **_):
        self.id = id

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "face", "data": {"id": str(self.id)}}


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


class Image(BaseMessageComponent):
    type = "Image"

    def __init__(self, file: str = "", url: str = "", path: str = "", **kwargs):
        self.file = file or url or path or ""
        self.url = url or (file if str(file).startswith(("http://", "https://")) else "")
        self.path = path or ("" if self.url else (file if isinstance(file, str) else ""))
        self.bytes_: bytes | None = kwargs.get("bytes_")

    @classmethod
    def fromURL(cls, url: str, **_):  # noqa: N802
        return cls(file=url, url=url)

    @classmethod
    def fromFileSystem(cls, path: str, **_):  # noqa: N802
        return cls(file=path, path=path)

    @classmethod
    def fromBytes(cls, data: bytes):  # noqa: N802
        obj = cls()
        obj.bytes_ = data
        return obj

    @classmethod
    def fromBase64(cls, b64: str):  # noqa: N802
        obj = cls()
        obj.file = f"base64://{b64}"
        return obj

    async def convert_to_base64(self) -> str:
        if self.bytes_ is not None:
            return _to_b64(self.bytes_)
        f = self.file
        if isinstance(f, bytes):
            return _to_b64(f)
        if isinstance(f, str):
            if f.startswith("base64://"):
                return f[len("base64://"):]
            if f.startswith(("http://", "https://")):
                import aiohttp

                async with aiohttp.ClientSession() as s, s.get(f) as r:
                    return _to_b64(await r.read())
            path = f[len("file://"):] if f.startswith("file://") else f
            if os.path.isfile(path):
                with open(path, "rb") as fp:
                    return _to_b64(fp.read())
        raise ValueError("无法转换图片为 base64")

    def _file_value(self) -> str:
        if self.bytes_ is not None:
            return f"base64://{_to_b64(self.bytes_)}"
        f = self.file
        if isinstance(f, bytes):
            return f"base64://{_to_b64(f)}"
        if isinstance(f, str):
            if f.startswith(("http://", "https://", "base64://", "file://")):
                return f
            if os.path.isabs(f) and os.path.isfile(f):
                return f"file://{f}"
            return f
        return ""

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "image", "data": {"file": self._file_value()}}


class At(BaseMessageComponent):
    type = "At"

    def __init__(self, qq=None, name: str = "", **_):
        self.qq = qq
        self.name = name or ""

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "at", "data": {"qq": str(self.qq)}}


class AtAll(BaseMessageComponent):
    type = "AtAll"

    def __init__(self, **_):
        self.qq = "all"

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "at", "data": {"qq": "all"}}


class Record(BaseMessageComponent):
    type = "Record"

    def __init__(self, file: str = "", url: str = "", path: str = "", **kwargs):
        self.file = file or url or path or ""
        self.url = url or ""
        self.path = path or ""
        self.bytes_: bytes | None = kwargs.get("bytes_")

    @classmethod
    def fromURL(cls, url: str, **_):  # noqa: N802
        return cls(file=url, url=url)

    @classmethod
    def fromFileSystem(cls, path: str, **_):  # noqa: N802
        return cls(file=path, path=path)

    async def convert_to_base64(self) -> str:
        if self.bytes_ is not None:
            return _to_b64(self.bytes_)
        f = self.file
        if isinstance(f, str) and f.startswith("base64://"):
            return f[len("base64://"):]
        path = f[len("file://"):] if isinstance(f, str) and f.startswith("file://") else f
        if isinstance(path, str) and os.path.isfile(path):
            with open(path, "rb") as fp:
                return _to_b64(fp.read())
        raise ValueError("无法转换语音为 base64")

    def _file_value(self) -> str:
        if self.bytes_ is not None:
            return f"base64://{_to_b64(self.bytes_)}"
        f = self.file
        if isinstance(f, str):
            if f.startswith(("http://", "https://", "base64://", "file://")):
                return f
            if os.path.isabs(f) and os.path.isfile(f):
                return f"file://{f}"
        return str(f)

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "record", "data": {"file": self._file_value()}}


class Video(BaseMessageComponent):
    type = "Video"

    def __init__(self, file: str = "", url: str = "", path: str = "", **_):
        self.file = file or url or path or ""
        self.url = url or ""
        self.path = path or ""

    @classmethod
    def fromURL(cls, url: str, **_):  # noqa: N802
        return cls(file=url, url=url)

    @classmethod
    def fromFileSystem(cls, path: str, **_):  # noqa: N802
        return cls(file=path, path=path)

    def _file_value(self) -> str:
        f = self.file
        if isinstance(f, str):
            if f.startswith(("http://", "https://", "base64://", "file://")):
                return f
            if os.path.isabs(f) and os.path.isfile(f):
                return f"file://{f}"
        return str(f)

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "video", "data": {"file": self._file_value()}}


class File(BaseMessageComponent):
    type = "File"

    def __init__(self, name: str = "", file: str = "", url: str = "", path: str = "", **_):
        self.name = name or ""
        self.file = file or path or url or ""
        self.url = url or ""
        self.path = path or file or ""

    def toDict(self) -> dict:  # noqa: N802
        f = self.file
        if isinstance(f, str) and os.path.isabs(f) and "://" not in f:
            f = f"file://{f}"
        return {"type": "file", "data": {"file": f, "name": self.name}}


class Reply(BaseMessageComponent):
    type = "Reply"

    def __init__(self, id=None, **kwargs):
        self.id = id if id is not None else kwargs.get("message_id")

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "reply", "data": {"id": str(self.id)}}


class Poke(BaseMessageComponent):
    type = "Poke"

    def __init__(self, qq=None, type=None, id=None, **_):
        self.qq = qq
        self.poke_type = type
        self.id = id

    def toDict(self) -> dict:  # noqa: N802
        data = {}
        if self.qq is not None:
            data["qq"] = str(self.qq)
        if self.id is not None:
            data["id"] = str(self.id)
        return {"type": "poke", "data": data}


class Json(BaseMessageComponent):
    type = "Json"

    def __init__(self, data="", **_):
        self.data = data

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "json", "data": {"data": self.data}}


class Node(BaseMessageComponent):
    """合并转发的单个节点。"""

    type = "Node"

    def __init__(self, content=None, uin=None, name: str = "", seq=None, time=None, **kwargs):
        self.content = content if content is not None else []
        self.uin = uin if uin is not None else kwargs.get("user_id")
        self.name = name or kwargs.get("nickname", "") or ""
        self.seq = seq
        self.time = time


class Nodes(BaseMessageComponent):
    """合并转发的节点列表。"""

    type = "Nodes"

    def __init__(self, nodes=None, **_):
        self.nodes = list(nodes) if nodes else []


class Forward(BaseMessageComponent):
    type = "Forward"

    def __init__(self, id=None, **_):
        self.id = id

    def toDict(self) -> dict:  # noqa: N802
        return {"type": "forward", "data": {"id": str(self.id)}}


class Unknown(BaseMessageComponent):
    type = "Unknown"

    def __init__(self, text: str = "", **_):
        self.text = text


class MessageChain:
    """AstrBot 消息链 (支持链式构造)。"""

    def __init__(self, chain=None, type="chain", **_):
        self.chain: list = list(chain) if chain else []
        self.type = type

    def message(self, text: str):
        self.chain.append(Plain(text))
        return self

    def text(self, text: str):
        self.chain.append(Plain(text))
        return self

    def file_image(self, file):
        self.chain.append(_image_from(file))
        return self

    def image(self, file):
        return self.file_image(file)

    def url_image(self, url):
        self.chain.append(Image.fromURL(url))
        return self

    def at(self, qq=None, name: str = ""):
        self.chain.append(At(qq=qq, name=name))
        return self

    def at_all(self):
        self.chain.append(AtAll())
        return self

    def face(self, id):
        self.chain.append(Face(id=id))
        return self

    def append(self, component):
        self.chain.append(component)
        return self

    def extend(self, components):
        self.chain.extend(components)
        return self

    def __iter__(self):
        return iter(self.chain)

    def get_plain_text(self) -> str:
        return "".join(c.text for c in self.chain if isinstance(c, Plain))


def _image_from(file):
    if isinstance(file, bytes):
        return Image.fromBytes(file)
    if isinstance(file, str) and file.startswith(("http://", "https://")):
        return Image.fromURL(file)
    return Image.fromFileSystem(file)


class MessageEventResult(MessageChain):
    """事件被动结果 (plain_result / image_result / chain_result 的返回类型)。"""

    def __init__(self, chain=None, result_type=None, **_):
        if isinstance(chain, MessageChain):
            super().__init__(list(chain.chain))
        else:
            super().__init__(list(chain) if chain else [])
        self.result_type = result_type
        self._use_t2i = None

    def use_t2i(self, enable: bool):
        self._use_t2i = enable
        return self
