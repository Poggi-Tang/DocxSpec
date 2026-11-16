"""Validated, versioned Studio document model shared by storage and rendering."""

import base64
import io
import math
import re

from PIL import Image

SCHEMA = "docxspec-studio-v1"
DEFAULT_TEXTS = [
    "测试报告\n产品名称：示例系统\n报告版本：V1.0",
    "测试环境：桌面浏览器\n测试范围：登录与权限校验",
    "",
    "暂无待处理问题。",
    "本轮测试完成，结果详见测试明细。",
]


def validate(data):
    if not isinstance(data, dict) or data.get("schema") not in (
        SCHEMA,
        "docxspec-studio-prototype-v1",
    ):
        raise ValueError("不支持的模板版本")

    def text(value, limit=20000):
        if (
            not isinstance(value, str)
            or len(value) > limit
            or any(ord(c) < 32 and c not in "\t\n\r" for c in value)
        ):
            raise ValueError("文本类型、长度或字符不合法")
        return value

    def choice(key, values):
        if data.get(key) not in values:
            raise ValueError(f"{key} 设置无效")
        return data[key]

    sections = data.get("sections")
    if not isinstance(sections, list) or not 3 <= len(sections) <= 50:
        raise ValueError("需要 3 至 50 个章节")
    sections = [text(s, 100) for s in sections]
    metadata = data.get("section_meta")
    if metadata is not None:
        if not isinstance(metadata, list) or len(metadata) != len(sections):
            raise ValueError("章节结构与章节数量不一致")
        cleaned_meta = []
        for entry in metadata:
            if not isinstance(entry, dict):
                raise ValueError("章节结构无效")
            kind, level = entry.get("kind"), entry.get("level")
            if kind not in ("cover", "revision", "toc", "figures", "tables", "heading", "cases"):
                raise ValueError("章节类型无效")
            if type(level) is not int or not 0 <= level <= 6:
                raise ValueError("标题级别无效")
            if (kind in ("heading", "cases")) != (level > 0):
                raise ValueError("章节类型与标题级别不一致")
            cleaned_meta.append(dict(kind=kind, level=level))
        if [entry["kind"] for entry in cleaned_meta[:5]] != [
            "cover", "revision", "toc", "figures", "tables"
        ] or any(entry["level"] == 0 for entry in cleaned_meta[5:]):
            raise ValueError("内置母版前置页结构无效")
        if sum(entry["kind"] == "cases" for entry in cleaned_meta) != 1:
            raise ValueError("需要且只能有一个测试用例章节")
        metadata = cleaned_meta
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) > 100:
        raise ValueError("测试用例最多 100 条")
    cleaned = []
    for c in cases:
        if not isinstance(c, dict):
            raise ValueError("测试用例必须为对象")
        item = {k: text(c.get(k)) for k in ("id", "name", "expected", "actual", "result")}
        steps = c.get("steps")
        if not isinstance(steps, list) or len(steps) > 200:
            raise ValueError("测试步骤必须为不超过 200 项的数组")
        item["steps"] = [text(s) for s in steps]
        if c.get("image"):
            image_bytes(c["image"])
            item["image"] = c["image"]
        cleaned.append(item)
    formats = data.get("format", {})
    texts = data.get("texts", {})
    if not isinstance(formats, dict) or not isinstance(texts, dict):
        raise ValueError("样式和章节内容必须为对象")
    result_formats = {}
    for key, f in formats.items():
        if not key.isdigit() or int(key) >= 100 or not isinstance(f, dict):
            raise ValueError("区块样式索引无效")
        value = dict(
            size=14,
            line="1",
            color="#f2f4f8",
            style="DS表格文字",
            bold=False,
            italic=False,
            center=False,
        )
        value.update({k: f[k] for k in value if k in f})
        if (
            type(value["size"]) not in (int, float)
            or not math.isfinite(value["size"])
            or not 12 <= value["size"] <= 28
        ):
            raise ValueError("字号范围为 12 至 28")
        if str(value["line"]) not in ("1", "1.5", "1.65", "2") or value["style"] not in (
            "DS正文", "DS主标题", "DS文档标题",
            "DS一级标题", "DS二级标题", "DS三级标题",
            "DS四级标题", "DS五级标题", "DS六级标题",
            "DS表格文字", "DS表格表头", "DS题注", "DS图片",
            "DS目录", "DS页眉", "DS页脚",
        ):
            raise ValueError("行距或样式无效")
        if not isinstance(value["color"], str) or not re.fullmatch(
            r"#[0-9a-fA-F]{6}", value["color"]
        ):
            raise ValueError("颜色无效")
        if any(type(value[k]) is not bool for k in ("bold", "italic", "center")):
            raise ValueError("样式开关无效")
        value["line"] = str(value["line"])
        result_formats[key] = {k: value[k] for k in value if k in f}
    for key in texts:
        if not key.isdigit() or int(key) >= len(sections):
            raise ValueError("章节索引无效")

    def index(key, maximum):
        v = data.get(key, 0)
        if type(v) is not int or not 0 <= v < max(1, maximum):
            raise ValueError("当前选中位置无效")
        return v

    result = dict(
        schema=SCHEMA,
        sections=sections,
        section=index("section", len(sections)),
        selected=index("selected", len(cleaned)),
        intro=text(data.get("intro", "")),
        source=choice("source", ["测试用例", "失败用例"]),
        repeat=choice("repeat", ["每条记录", "仅首条记录"]),
        empty=choice("empty", ["隐藏区块", "显示待补充"]),
        cases=cleaned,
        format=result_formats,
        texts={k: text(v) for k, v in texts.items()},
    )

    if metadata is not None:
        result["section_meta"] = metadata
    return result


def image_bytes(value):
    if not isinstance(value, str) or not re.match(
        r"^data:image/(png|jpeg|jpg|webp|gif);base64,", value
    ):
        raise ValueError("截图仅支持 PNG、JPEG、WebP 或 GIF")
    try:
        raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError("截图不能超过 5 MB")
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("截图不能超过 2000 万像素")
            image.verify()
        return raw
    except Exception as exc:
        raise ValueError("截图损坏或超过大小限制") from exc
