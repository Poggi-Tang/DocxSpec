"""Component and page models used by both Python reports and Studio."""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid() -> str:
    return uuid.uuid4().hex


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: float | None = Field(default=None, ge=5, le=72)
    font: str | None = Field(default=None, max_length=80)
    bold: bool | None = None
    italic: bool | None = None
    align: Literal["left", "center", "right", "justify"] | None = None
    before: float | None = Field(default=None, ge=0, le=144)
    after: float | None = Field(default=None, ge=0, le=144)
    line: float | None = Field(default=None, ge=1, le=3)
    color: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{6}$")


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=uid, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: Literal[
        "heading",
        "paragraph",
        "table",
        "caption",
        "image",
        "repeat",
        "condition",
        "group",
        "pagebreak",
        "section",
        "toc",
    ]
    label: str = Field(default="", max_length=100)
    text: str = Field(default="", max_length=30000)
    level: int = Field(default=1, ge=1, le=6)
    style: Style = Field(default_factory=Style)
    rows: list[list[str]] = Field(
        default_factory=lambda: [["测试项", "结果"], ["{{item.name}}", "{{item.result}}"]],
        max_length=200,
    )
    rows_source: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=200)
    equals: str = Field(default="", max_length=1000)
    empty: Literal["hide", "placeholder"] = "hide"
    target: str = Field(default="", max_length=64)
    caption_type: Literal["table", "figure"] = "table"
    numbering: Literal["chapter", "document"] = "chapter"
    asset: str = Field(default="", pattern=r"^(|[a-f0-9]{64})$")
    width: float = Field(default=14, ge=1, le=25)
    columns: list[float] = Field(default_factory=list, max_length=20)
    header_rows: int = Field(default=1, ge=0, le=10)
    children: list[Node] = Field(default_factory=list, max_length=300)
    component_id: str | None = None
    component_version: int | None = None

    @model_validator(mode="after")
    def check(self):
        if self.kind not in ("repeat", "condition", "group", "section") and self.children:
            raise ValueError("此组件不能包含子组件")
        if self.kind == "table":
            if (
                not self.rows
                or not self.rows[0]
                or len(self.rows[0]) > 20
                or any(len(r) != len(self.rows[0]) for r in self.rows)
            ):
                raise ValueError("表格必须为 1 至 20 列的矩形")
            if any(len(c) > 30000 for r in self.rows for c in r):
                raise ValueError("单元格内容过长")
            if self.columns and (
                len(self.columns) != len(self.rows[0])
                or any(v <= 0 or v > 25 for v in self.columns)
            ):
                raise ValueError("列宽必须与表格列数一致")
        for path in (self.source, self.rows_source):
            if path and not re.fullmatch(r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*", path):
                raise ValueError("字段路径格式不合法")
        return self


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: float = Field(default=21, ge=10, le=42)
    height: float = Field(default=29.7, ge=10, le=60)
    margin: float = Field(default=2.5, ge=0.5, le=5)

    @model_validator(mode="after")
    def check(self):
        if min(self.width, self.height) <= 2 * self.margin + 2:
            raise ValueError("页边距超出可用版心")
        return self


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["docxspec-studio-v2"] = "docxspec-studio-v2"
    nodes: list[Node] = Field(default_factory=list, max_length=300)
    header: str = Field(default="", max_length=3000)
    footer: str = Field(default="第 {PAGE} 页 / 共 {NUMPAGES} 页", max_length=3000)
    page: Page = Field(default_factory=Page)

    @model_validator(mode="after")
    def check(self):
        ids = set()

        def walk(nodes, depth=0):
            if depth > 6:
                raise ValueError("组件嵌套不能超过 6 层")
            for n in nodes:
                if n.id in ids:
                    raise ValueError("组件 ID 重复")
                ids.add(n.id)
                if len(ids) > 1000:
                    raise ValueError("组件总数不能超过 1000")
                walk(n.children, depth + 1)

        walk(self.nodes)
        return self
