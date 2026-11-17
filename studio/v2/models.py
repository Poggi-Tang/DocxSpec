from __future__ import annotations

import copy
import re
import uuid
from typing import Any, Literal

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


class TemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    set_id: str
    document: DocumentModel
    data: dict[str, Any] = Field(default_factory=dict)
    version: int | None = None


def clone_node(node: dict) -> dict:
    result = copy.deepcopy(node)
    mapping = {}

    def assign(n):
        old = n["id"]
        n["id"] = uid()
        mapping[old] = n["id"]
        for child in n.get("children", []):
            assign(child)

    def refs(n):
        if n.get("target"):
            n["target"] = mapping.get(n["target"], "")
        for child in n.get("children", []):
            refs(child)

    assign(result)
    refs(result)
    return result


def presets():
    specs = [
        ("一级标题", dict(kind="heading", text="测试结果")),
        ("正文", dict(kind="paragraph", text="请输入报告说明。")),
        (
            "表格",
            dict(
                kind="table",
                rows=[["测试项", "预期结果", "实际结果"], ["登录功能", "进入首页", "通过"]],
            ),
        ),
        ("表格题注", dict(kind="caption", text="测试结果汇总")),
        ("图片", dict(kind="image")),
        ("图片题注", dict(kind="caption", caption_type="figure", text="测试截图")),
        (
            "重复区块",
            dict(
                kind="repeat",
                source="testCases",
                children=[dict(kind="paragraph", text="{{item.name}}：{{item.result}}")],
            ),
        ),
        (
            "条件区块",
            dict(
                kind="condition",
                source="showConclusion",
                equals="true",
                children=[dict(kind="paragraph", text="测试结论")],
            ),
        ),
        ("分页", dict(kind="pagebreak")),
        ("分节", dict(kind="section", children=[dict(kind="paragraph", text="新节正文")])),
        ("目录", dict(kind="toc")),
    ]
    return [
        dict(
            id="builtin-" + str(i),
            name=name,
            version=1,
            node=Node(label=name, **spec).model_dump(),
            builtin=True,
        )
        for i, (name, spec) in enumerate(specs)
    ]


def initial_document():
    return DocumentModel(
        nodes=[
            Node(kind="heading", text="测试结果", label="测试结果"),
            Node(kind="paragraph", text="项目名称：{{project.name}}"),
            Node(
                kind="repeat",
                label="测试用例",
                source="testCases",
                children=[
                    Node(kind="heading", level=2, text="{{item.name}}"),
                    Node(
                        kind="table",
                        rows=[
                            ["测试步骤", "预期结果", "实际结果"],
                            ["{{item.steps}}", "{{item.expected}}", "{{item.result}}"],
                        ],
                    ),
                ],
            ),
        ]
    ).model_dump()


def initial_data():
    return {
        "project": {"name": "示例系统"},
        "testCases": [
            {
                "name": "登录功能测试",
                "steps": "输入用户名和密码，点击登录。",
                "expected": "进入系统首页",
                "result": "通过",
            }
        ],
    }
