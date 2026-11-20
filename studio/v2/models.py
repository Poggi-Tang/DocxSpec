"""Studio persistence inputs and built-in component templates."""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from docxspec.report._models import DocumentModel, Node, Page, Style, uid

__all__ = [
    "DocumentModel",
    "Node",
    "Page",
    "Style",
    "TemplateInput",
    "clone_node",
    "initial_data",
    "initial_document",
    "presets",
    "uid",
]


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
            Node(kind="heading", text="测试结果"),
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
