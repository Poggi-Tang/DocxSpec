"""Compile the validated component tree using the controlled DS master only."""

import copy
import re
from collections.abc import Callable
from pathlib import Path

from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from docxspec import (
    DEFAULT_MASTER_TEMPLATE,
    CellStyle,
    TableStyle,
    TextStyle,
    WordAPI,
    mark_update_fields_on_open,
)

from ._models import DocumentModel

TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
LEVELS = "一二三四五六"


def lookup(data, path):
    value = data
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"缺少数据字段：{path}")
        value = value[key]
    return value


def fill(text, data):
    def replace(match):
        value = lookup(data, match[1])
        if value is None:
            raise ValueError(f"字段为空：{match[1]}")
        if isinstance(value, list):
            return "\n".join(str(x) for x in value)
        if isinstance(value, dict):
            raise ValueError(f"文本字段不能绑定对象：{match[1]}")
        return str(value)

    return TOKEN.sub(replace, text)


def field(paragraph, code, cache=""):
    for tag, attrs, text in [
        ("fldChar", {"fldCharType": "begin", "dirty": "true"}, None),
        ("instrText", {}, code),
        ("fldChar", {"fldCharType": "separate"}, None),
    ]:
        el = OxmlElement("w:" + tag)
        for k, v in attrs.items():
            el.set(qn("w:" + k), v)
        if text is not None:
            el.text = text
            el.set(qn("xml:space"), "preserve")
        paragraph.add_run()._r.append(el)
    paragraph.add_run(cache)
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(el)


def style_name(n):
    return {
        "heading": f"DS{LEVELS[n['level'] - 1]}级标题",
        "caption": "DS题注",
        "image": "DS图片",
        "table": "DS表格文字",
    }.get(n["kind"], "DS正文")


def expand(nodes, data, repeat_scope=(), result=None, *, check_cancelled=None):
    if result is None:
        result = []
    for node in nodes:
        if check_cancelled is not None:
            check_cancelled()
        n = copy.deepcopy(node)
        n["origin_id"] = n["id"]
        n["repeat_scope"] = repeat_scope
        n["occurrence"] = n["id"] + "".join(f"_{index}" for _, index in repeat_scope)
        if n["kind"] == "repeat":
            records = lookup(data, n["source"])
            if not isinstance(records, list) or len(records) > 200:
                raise ValueError("重复数据必须为最多 200 条的数组")
            if not records and n["empty"] == "placeholder":
                result.append({**n, "kind": "paragraph", "text": "数据待补充"})
            for i, item in enumerate(records):
                expand(
                    n["children"], {**data, "item": item}, (*repeat_scope, (n["id"], i)), result,
                    check_cancelled=check_cancelled,
                )
        elif n["kind"] == "condition":
            value = lookup(data, n["source"])
            display = str(value).lower() if isinstance(value, bool) else str(value)
            if display == n["equals"]:
                expand(n["children"], data, repeat_scope, result, check_cancelled=check_cancelled)
        elif n["kind"] == "group":
            expand(n["children"], data, repeat_scope, result, check_cancelled=check_cancelled)
        elif n["kind"] == "section":
            result.append(n)
            expand(n["children"], data, repeat_scope, result, check_cancelled=check_cancelled)
        else:
            if n["kind"] == "caption":
                # A caption for an omitted table never needs its fields resolved.
                n["caption_data"] = data
            else:
                n["text"] = fill(n["text"], data)
            if n["kind"] == "image" and n["source"]:
                n["asset"] = str(lookup(data, n["source"]))
            if n["kind"] == "table":
                if n["rows_source"]:
                    records = lookup(data, n["rows_source"])
                    if not isinstance(records, list) or len(records) > 200:
                        raise ValueError("重复行数据最多 200 条")
                    head = n["rows"][: n["header_rows"]]
                    tail = n["rows"][n["header_rows"] :]
                    n["rows"] = [[fill(c, data) for c in row] for row in head] + [
                        [fill(c, {**data, "row": item}) for c in row]
                        for item in records
                        for row in tail
                    ]
                else:
                    n["rows"] = [[fill(c, data) for c in row] for row in n["rows"]]
            result.append(n)
        if len(result) > 2000:
            raise ValueError("展开后组件数量不能超过 2000")
    return result


def compile_document(
    model: DocumentModel,
    data: dict,
    assets: Path,
    output: Path,
    *,
    asset_resolver: Callable[[str], Path] | None = None,
    check_cancelled: Callable[[], None] | None = None,
):
    api = WordAPI(str(DEFAULT_MASTER_TEMPLATE))
    doc = api.doc.get_docx()
    body = doc.element.body
    for el in list(body):
        if el.tag != qn("w:sectPr"):
            body.remove(el)
    props = model.page
    section = doc.sections[0]
    section.page_width = Cm(props.width)
    section.page_height = Cm(props.height)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Cm(
        props.margin
    )
    for area, text, style in [
        (section.header, model.header, "DS页眉"),
        (section.footer, model.footer, "DS页脚"),
    ]:
        for el in list(area._element):
            area._element.remove(el)
        p = area.add_paragraph(style=style)
        parts = re.split(r"(\{PAGE\}|\{NUMPAGES\})", fill(text, data))
        for part in parts:
            if part in ("{PAGE}", "{NUMPAGES}"):
                field(p, part[1:-1], "1")
            else:
                p.add_run(part)
    section.different_first_page_header_footer = False
    doc.settings.odd_and_even_pages_header_footer = False
    nodes = expand([n.model_dump() for n in model.nodes], data, check_cancelled=check_cancelled)
    # Caption references follow actual expanded objects, never the array's selected index.
    chapter = 0
    counts = {}
    numbers = {}
    omitted_tables = set()
    for n in nodes:
        if n["kind"] == "heading" and n["level"] == 1:
            chapter += 1
        if n["kind"] == "table" and not n["rows"]:
            omitted_tables.add((n["id"], n["repeat_scope"]))
        elif n["kind"] in ("image", "table"):
            kind = n["kind"]
            counts[(chapter, kind)] = counts.get((chapter, kind), 0) + 1
            counts[("all", kind)] = counts.get(("all", kind), 0) + 1
            numbers[(n["id"], n["repeat_scope"])] = {
                "chapter": f"{chapter}-{counts[(chapter, kind)]}",
                "document": str(counts[("all", kind)]),
                "kind": kind,
            }
    anchors = []
    width = props.width - 2 * props.margin
    for index, n in enumerate(nodes):
        if check_cancelled is not None:
            check_cancelled()
        s = {k: v for k, v in n["style"].items() if v is not None}
        name = style_name(n)
        text_style = TextStyle(
            style_name=name,
            font_name=s.get("font"),
            font_size=s.get("size"),
            bold=s.get("bold"),
            italic=s.get("italic"),
            align=s.get("align"),
            line_spacing=s.get("line"),
            space_before_pt=s.get("before"),
            space_after_pt=s.get("after"),
            font_color=s.get("color"),
        )
        kind = n["kind"]
        following = nodes[index + 1] if index + 1 < len(nodes) else {}
        caption_follows = (
            following.get("kind") == "caption"
            and following["target"] == n["id"]
            and following["repeat_scope"] == n["repeat_scope"]
        )
        p = None
        anchor_text = n["text"]
        if kind == "caption":
            target_key = (n["target"], n["repeat_scope"])
            if n["caption_type"] == "table" and target_key in omitted_tables:
                continue
            target = numbers.get(target_key)
            if not target or target["kind"] != (
                "table" if n["caption_type"] == "table" else "image"
            ):
                raise ValueError("题注需要关联同一重复范围内的表格或图片")
            anchor_text = (
                ("表 " if n["caption_type"] == "table" else "图 ")
                + target[n["numbering"]]
                + " "
                + fill(n["text"], n["caption_data"])
            )
            p = api.add_paragraph(doc, anchor_text, text_style)
        elif kind in ("heading", "paragraph"):
            p = api.add_paragraph(doc, n["text"], text_style)
            if kind == "heading":
                p.paragraph_format.keep_with_next = True
        elif kind == "table":
            if not n["rows"]:
                continue
            cell = CellStyle(
                paragraph_style_name="DS表格文字",
                font_name=s.get("font"),
                font_size=s.get("size"),
                bold=s.get("bold"),
                italic=s.get("italic"),
                align=s.get("align"),
                line_spacing=s.get("line"),
                font_color=s.get("color"),
            )
            header = copy.copy(cell)
            header.paragraph_style_name = "DS表格表头"
            widths = n["columns"] or [width / len(n["rows"][0])] * len(n["rows"][0])
            if sum(widths) > width + 0.01:
                raise ValueError("表格列宽之和超过页面可用宽度")
            table = api.insert_table(
                doc,
                [[{"text": c} for c in r] for r in n["rows"]],
                header_style=header,
                body_style=cell,
                table_style=TableStyle(col_widths_cm=widths, header_rows=n["header_rows"]),
            )
            for i, row in enumerate(table.rows):
                row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                if i < n["header_rows"]:
                    row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                if text_style.space_before_pt is not None or text_style.space_after_pt is not None:
                    for table_cell in row.cells:
                        for paragraph in table_cell.paragraphs:
                            if text_style.space_before_pt is not None:
                                paragraph.paragraph_format.space_before = Pt(
                                    text_style.space_before_pt
                                )
                            if text_style.space_after_pt is not None:
                                paragraph.paragraph_format.space_after = Pt(
                                    text_style.space_after_pt
                                )
            if caption_follows:
                for last_cell in table.rows[-1].cells:
                    for paragraph in last_cell.paragraphs:
                        paragraph.paragraph_format.keep_with_next = True
            p = table.cell(0, 0).paragraphs[0]
            anchor_text = ""
        elif kind == "image":
            if not re.fullmatch(r"[a-f0-9]{64}", n["asset"]):
                raise ValueError("请为图片组件上传图片或绑定图片字段")
            asset = assets / n["asset"] if asset_resolver is None else asset_resolver(n["asset"])
            if not asset.is_file():
                raise ValueError("图片资源不存在")
            p = api.add_paragraph(doc, "", text_style)
            from PIL import Image

            with Image.open(asset) as image:
                w, h = image.size
            scale = min(n["width"], width, (props.height - 2 * props.margin - 2) * w / h)
            p.add_run().add_picture(str(asset), width=Cm(scale))
            if caption_follows:
                p.paragraph_format.keep_with_next = True
            anchor_text = ""
        elif kind == "pagebreak":
            doc.add_page_break()
        elif kind == "section":
            doc.add_section(WD_SECTION_START.NEW_PAGE)
        elif kind == "toc":
            p = doc.add_paragraph(style="DS目录")
            field(p, 'TOC \\o "1-6" \\h \\z \\u', "目录待目标 Office 刷新")
            anchor_text = ""
        if p is not None:
            # Bookmark does not introduce hidden marker text or change line layout.
            start = OxmlElement("w:bookmarkStart")
            start.set(qn("w:id"), str(1000 + index))
            start.set(qn("w:name"), "DSN_" + str(index))
            p._p.insert(1 if p._p.pPr is not None else 0, start)
            end = OxmlElement("w:bookmarkEnd")
            end.set(qn("w:id"), str(1000 + index))
            p._p.append(end)
        anchors.append(
            dict(node_id=n["origin_id"], occurrence=n["occurrence"], text=anchor_text, kind=kind)
        )
    doc.core_properties.author = "DocxSpec"
    doc.core_properties.last_modified_by = "DocxSpec"
    doc.core_properties.title = "测试报告"
    if check_cancelled is not None:
        check_cancelled()
    doc.save(output)
    mark_update_fields_on_open(output)
    return anchors
