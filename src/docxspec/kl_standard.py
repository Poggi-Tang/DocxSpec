"""KL 标准 Word 文档处理能力。

本模块把公司 Word 标准化流程沉淀为 DocxSpec 的库能力。它不绑定 GUI，
只提供可复用的 DOCX 分类、样式规范化、题注字段、标准文档构建和检查入口。
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from docx import Document
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docxcompose.composer import Composer

PACKAGE_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_MASTER_TEMPLATE = PACKAGE_ASSETS_DIR / "docxspec_master_template.docx"

STYLE_MAIN_TITLE = "KL主标题"
STYLE_HEADING_1 = "KL一级标题"
STYLE_HEADING_2 = "KL二级标题"
STYLE_HEADING_3 = "KL三级标题"
STYLE_HEADING_OTHER = "KL其他标题"
STYLE_BODY = "KL正文"
STYLE_CAPTION = "KL题注"
STYLE_TABLE_HEADER = "KL表格表头"
STYLE_TABLE_BODY = "KL表格文字"
STYLE_IMAGE = "KL图片"

REQUIRED_STYLES = [
    STYLE_HEADING_1,
    STYLE_HEADING_2,
    STYLE_HEADING_3,
    STYLE_HEADING_OTHER,
    STYLE_BODY,
    STYLE_CAPTION,
    STYLE_TABLE_HEADER,
    STYLE_TABLE_BODY,
]

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
}

STYLE_TO_TYPE = {
    STYLE_HEADING_1: ("heading_1", "high"),
    "Heading 1": ("heading_1", "high"),
    "标题 1": ("heading_1", "high"),
    "1": ("heading_1", "medium"),
    STYLE_HEADING_2: ("heading_2", "high"),
    "Heading 2": ("heading_2", "high"),
    "标题 2": ("heading_2", "high"),
    "2": ("heading_2", "medium"),
    STYLE_HEADING_3: ("heading_3", "high"),
    "Heading 3": ("heading_3", "high"),
    "标题 3": ("heading_3", "high"),
    "3": ("heading_3", "medium"),
    STYLE_HEADING_OTHER: ("heading_other", "high"),
}

CHINESE_NUM = "一二三四五六七八九十百千万〇零两"
H1_EXACT_TITLES = {"需求背景", "从需求分析到方案落地", "示例演示", "总结"}

NUMBER_PREFIX_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("heading_1", re.compile(rf"^第?\s*[{CHINESE_NUM}]+\s*[章节篇部分]\s*[、.．:：]?\s*")),
    ("heading_1", re.compile(rf"^[{CHINESE_NUM}]+[、.．]\s*")),
    ("heading_1", re.compile(r"^\d+[、．]\s*|^\d+\s+")),
    ("heading_3", re.compile(r"^\d+[.．]\d+[.．]\d+[、.．]?\s*")),
    ("heading_2", re.compile(r"^\d+[.．]\d+[、.．]?\s*")),
    ("heading_2", re.compile(rf"^[（(]\s*[{CHINESE_NUM}]+\s*[）)]\s*")),
    ("heading_2", re.compile(rf"^[{CHINESE_NUM}]+[）)]\s*")),
    ("heading_3", re.compile(r"^[（(]\s*\d+\s*[）)]\s*")),
    ("heading_3", re.compile(r"^\d+[）)]\s*")),
]

CAPTION_TEXT_PATTERNS = {
    "figure_caption": re.compile(r"^\s*图\s*[\d一二三四五六七八九十]+[-－—.．]\d+\s+\S+"),
    "table_caption": re.compile(r"^\s*表\s*[\d一二三四五六七八九十]+[-－—.．]\d+\s+\S+"),
}


@dataclass
class BlockReport:
    """DOCX 正文块分类结果。"""

    index: int
    kind: str
    type: str
    text: str = ""
    style_id: str | None = None
    style_name: str | None = None
    reason: str | None = None
    confidence: str | None = None
    has_figure: bool = False
    field_codes: list[str] | None = None
    rows: int | None = None
    columns: int | None = None
    caption: dict[str, Any] | None = None


def iter_block_items(doc: Document) -> list[Paragraph | Table]:
    """按 Word 正文顺序返回段落和表格块。"""
    blocks: list[Paragraph | Table] = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            blocks.append(Paragraph(child, doc))
        elif child.tag == qn("w:tbl"):
            blocks.append(Table(child, doc))
    return blocks


def paragraph_has_image(paragraph: Paragraph) -> bool:
    """判断段落中是否包含图片。"""
    return bool(paragraph._element.xpath(".//w:drawing") or paragraph._element.xpath(".//w:pict"))


def paragraph_field_xml(paragraph: Paragraph) -> str:
    """返回段落 XML，用于检查域代码。"""
    return paragraph._element.xml


def style_name(paragraph: Paragraph) -> str:
    """安全获取段落样式名称。"""
    try:
        return paragraph.style.name or ""
    except Exception:
        return ""


def set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    """替换段落纯文本。"""
    paragraph.text = text


def clear_numbering(paragraph: Paragraph) -> None:
    """清除段落自身编号设置，让 KL 标题样式接管编号。"""
    ppr = paragraph._element.get_or_add_pPr()
    for num_pr in list(ppr.findall(qn("w:numPr"))):
        ppr.remove(num_pr)


def normalize_paragraph_to_style(paragraph: Paragraph, style: str) -> None:
    """应用段落样式，并清理直接格式和非样式段落属性。"""
    paragraph.style = style
    ppr = paragraph._element.get_or_add_pPr()
    for child in list(ppr):
        if child.tag != qn("w:pStyle"):
            ppr.remove(child)
    for run in paragraph.runs:
        rpr = run._element.find(qn("w:rPr"))
        if rpr is not None:
            run._element.remove(rpr)


def normalize_table_cell_paragraph(paragraph: Paragraph, style: str) -> None:
    """应用表格单元格段落样式。"""
    normalize_paragraph_to_style(paragraph, style)


def clean_heading_number(text: str) -> tuple[str, str | None]:
    """移除常见手工标题序号，并返回推断的标题类型。"""
    stripped = text.strip()
    for kind, pattern in NUMBER_PREFIX_PATTERNS:
        cleaned = pattern.sub("", stripped, count=1).strip()
        if cleaned != stripped and cleaned:
            return cleaned, kind
    return stripped, None


def is_short_heading_candidate(text: str) -> bool:
    """判断短文本是否可作为普通标题候选。"""
    if not text or len(text) > 32:
        return False
    if "http://" in text or "https://" in text:
        return False
    if "：" in text or ":" in text:
        return False
    if text.endswith(("。", "；", ";", "，", ",")):
        return False
    return True


def classify_heading(text: str, paragraph: Paragraph | None = None) -> tuple[str, str, str, str]:
    """按文本和已有样式判断段落应使用的 KL 标题/正文类型。"""
    raw = text.strip()
    if re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", raw):
        return "body", raw, "circled-number item is body, not heading", "high"
    cleaned, numbered_kind = clean_heading_number(raw)
    if numbered_kind:
        if len(cleaned) > 42:
            return "body", raw, "numbered text too long to classify as heading", "medium"
        return numbered_kind, cleaned, "matched numbered heading prefix", "high"

    if paragraph is not None:
        raw_style = style_name(paragraph)
        normalized = raw_style.replace(" ", "").lower()
        if raw_style in {STYLE_HEADING_1, "标题 1", "Heading 1"} or normalized in {"heading1", "1"}:
            return "heading_1", raw, "matched heading-1 style", "high"
        if raw_style in {STYLE_HEADING_2, "标题 2", "Heading 2"} or normalized in {"heading2", "2"}:
            return "heading_2", raw, "matched heading-2 style", "high"
        if raw_style in {STYLE_HEADING_3, "标题 3", "Heading 3"} or normalized in {"heading3", "3"}:
            return "heading_3", raw, "matched heading-3 style", "high"

    if raw in H1_EXACT_TITLES:
        return "heading_1", raw, "matched known major section title", "high"
    if is_short_heading_candidate(raw):
        return "heading_2", raw, "short standalone title line", "medium"
    return "body", raw, "default body paragraph", "low"


def document_has_figures(docx: Path) -> bool:
    """判断文档是否包含图片。"""
    doc = Document(str(docx))
    return any(paragraph_has_image(p) for p in doc.paragraphs)


def document_has_tables(docx: Path) -> bool:
    """判断文档是否包含表格。"""
    doc = Document(str(docx))
    return bool(doc.tables)


def first_nonblank_paragraph_text(docx: Path) -> str | None:
    """读取文档第一个非空段落文本，通常作为封面标题候选。"""
    doc = Document(str(docx))
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            return clean_heading_number(text)[0]
    return None


def remove_block(block: Paragraph | Table) -> None:
    """从文档 XML 中删除段落或表格块。"""
    element = block._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def remove_template_sample_body(doc: Document) -> int:
    """删除母版中的示例正文，保留封面、目录、图表清单等前置内容。"""
    blocks = iter_block_items(doc)
    start_idx: int | None = None
    for idx, block in enumerate(blocks):
        if isinstance(block, Paragraph):
            if block.text.strip() == STYLE_HEADING_1 or style_name(block) == STYLE_HEADING_1:
                start_idx = idx
                break
    if start_idx is None:
        return len(blocks)
    for block in blocks[start_idx:]:
        remove_block(block)
    return start_idx


def replace_cover_title(doc: Document, title: str | None) -> None:
    """把母版封面标题替换为源文档标题。"""
    if not title:
        return
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text == "XXXX系统":
            paragraph.text = title
            normalize_paragraph_to_style(paragraph, STYLE_MAIN_TITLE)
        elif text == "技术方案":
            paragraph.text = ""


def set_default_headers(doc: Document, title: str | None) -> None:
    """把所有节的页眉设置为标题。"""
    if not title:
        return
    for section in doc.sections:
        for header in (section.header, section.even_page_header):
            if not header.paragraphs:
                header.add_paragraph(title)
            for paragraph in header.paragraphs:
                paragraph.text = title


def insert_paragraph_after(paragraph: Paragraph, style: str | None = None) -> Paragraph:
    """在指定段落后插入新段落。"""
    new_p = OxmlElement("w:p")
    paragraph._element.addnext(new_p)
    new_paragraph = Paragraph(new_p, paragraph._parent)
    if style:
        new_paragraph.style = style
    return new_paragraph


def append_field(run: Any, instr: str, placeholder: str) -> None:
    """向 run 中追加 Word 域代码。"""
    r = run._r
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    r.append(begin)

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = instr
    r.append(instr_text)

    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    r.append(separate)

    text = OxmlElement("w:t")
    text.text = placeholder
    r.append(text)

    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    r.append(end)


def has_figure_caption_field(paragraph: Paragraph) -> bool:
    """判断段落是否包含图题注 SEQ 域。"""
    return "SEQ 图" in paragraph_field_xml(paragraph)


def has_table_caption_field(paragraph: Paragraph) -> bool:
    """判断段落是否包含表题注 SEQ 域。"""
    return "SEQ 表" in paragraph_field_xml(paragraph)


def add_figure_caption_after(
    paragraph: Paragraph,
    caption_text: str,
    chapter_no: int = 1,
    figure_no: int = 1,
) -> None:
    """在图片段落后插入 KL 图题注和必要空行。"""
    caption = insert_paragraph_after(paragraph, STYLE_CAPTION)
    normalize_paragraph_to_style(caption, STYLE_CAPTION)
    caption.add_run("图 ")
    append_field(caption.add_run(), r" STYLEREF KL一级标题 \n \* MERGEFORMAT ", str(chapter_no))
    caption.add_run("-")
    append_field(caption.add_run(), r" SEQ 图 \* ARABIC \s 1 ", str(figure_no))
    caption.add_run(f" {caption_text}")
    blank = insert_paragraph_after(caption, STYLE_BODY)
    normalize_paragraph_to_style(blank, STYLE_BODY)


def make_context_caption(
    heading_1: str | None,
    heading_2: str | None,
    heading_3: str | None,
    figure_no: int = 1,
) -> str:
    """根据附近标题生成缺省图片题注名称。"""
    del figure_no
    for heading in (heading_2, heading_1, heading_3):
        if heading:
            base = heading[:18]
            return base if base.endswith("图") else f"{base}图"
    return "示意图"


def next_nonblank_block(blocks: list[Paragraph | Table], start: int) -> Paragraph | Table | None:
    """获取后续第一个非空正文块。"""
    for block in blocks[start + 1 :]:
        if isinstance(block, Table):
            return block
        if isinstance(block, Paragraph) and (block.text.strip() or paragraph_has_image(block)):
            return block
    return None


def previous_block(blocks: list[Paragraph | Table], start: int) -> Paragraph | Table | None:
    """获取前一个正文块。"""
    if start <= 0:
        return None
    return blocks[start - 1]


def should_keep_blank(blocks: list[Paragraph | Table], idx: int) -> bool:
    """判断空段落是否是题注规范要求保留的空行。"""
    prev_block = previous_block(blocks, idx)
    next_block = blocks[idx + 1] if idx + 1 < len(blocks) else None
    if isinstance(prev_block, Paragraph) and (
        has_figure_caption_field(prev_block) or has_table_caption_field(prev_block)
    ):
        return True
    if isinstance(next_block, Paragraph) and has_table_caption_field(next_block):
        return True
    return False


def ensure_blank_before_paragraph(paragraph: Paragraph) -> None:
    """确保一级标题前有一个 KL 正文样式空段落。"""
    prev = paragraph._element.getprevious()
    if prev is not None and prev.tag == qn("w:p"):
        prev_para = Paragraph(prev, paragraph._parent)
        if not prev_para.text.strip() and not paragraph_has_image(prev_para):
            normalize_paragraph_to_style(prev_para, STYLE_BODY)
            return
    new_p = OxmlElement("w:p")
    paragraph._element.addprevious(new_p)
    blank = Paragraph(new_p, paragraph._parent)
    normalize_paragraph_to_style(blank, STYLE_BODY)


def apply_table_styles(table: Table) -> None:
    """给表格首行和表体应用 KL 表格样式。"""
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                normalize_table_cell_paragraph(
                    paragraph,
                    STYLE_TABLE_HEADER if row_idx == 0 else STYLE_TABLE_BODY,
                )


def standardize_appended_body(
    doc: Document,
    start_idx: int,
    source_title: str | None = None,
) -> dict[str, Any]:
    """规范化追加到母版后的正文块。"""
    blocks = iter_block_items(doc)
    report: dict[str, Any] = {
        "styled": [],
        "figure_captions_added": [],
        "tables_styled": 0,
        "removed_duplicate_body_title": False,
        "number_prefixes_removed": [],
    }
    current_chapter_no = 0
    current_heading_1: str | None = None
    current_heading_2: str | None = None
    current_heading_3: str | None = None
    figure_no_by_chapter: dict[int, int] = {}
    idx = start_idx

    while idx < len(blocks):
        block = blocks[idx]
        if isinstance(block, Table):
            apply_table_styles(block)
            report["tables_styled"] += 1
            idx += 1
            continue

        text = block.text.strip()
        cleaned_text = clean_heading_number(text)[0]
        if (
            source_title
            and cleaned_text == source_title
            and not report["removed_duplicate_body_title"]
        ):
            remove_block(block)
            report["removed_duplicate_body_title"] = True
            blocks = iter_block_items(doc)
            continue

        if paragraph_has_image(block):
            normalize_paragraph_to_style(block, STYLE_IMAGE)
            next_block = blocks[idx + 1] if idx + 1 < len(blocks) else None
            if not (isinstance(next_block, Paragraph) and has_figure_caption_field(next_block)):
                chapter_no = max(current_chapter_no, 1)
                figure_no_by_chapter[chapter_no] = figure_no_by_chapter.get(chapter_no, 0) + 1
                figure_no = figure_no_by_chapter[chapter_no]
                caption_text = make_context_caption(
                    current_heading_1,
                    current_heading_2,
                    current_heading_3,
                    figure_no,
                )
                add_figure_caption_after(block, caption_text, chapter_no, figure_no)
                report["figure_captions_added"].append(
                    {
                        "after_block": idx,
                        "chapter": chapter_no,
                        "figure": figure_no,
                        "caption": caption_text,
                    }
                )
                blocks = iter_block_items(doc)
            idx += 1
            continue

        if not text:
            if should_keep_blank(blocks, idx):
                normalize_paragraph_to_style(block, STYLE_BODY)
            else:
                remove_block(block)
                blocks = iter_block_items(doc)
                continue
            idx += 1
            continue

        if has_figure_caption_field(block) or has_table_caption_field(block):
            normalize_paragraph_to_style(block, STYLE_CAPTION)
            idx += 1
            continue

        kind, clean_text, reason, confidence = classify_heading(text, block)
        following = next_nonblank_block(blocks, idx)
        if (
            kind == "heading_2"
            and reason == "short standalone title line"
            and isinstance(following, Paragraph)
            and paragraph_has_image(following)
        ):
            kind = "body"
            clean_text = text
            reason = "short image context line preserved as body"
            confidence = "medium"

        if kind.startswith("heading_"):
            clear_numbering(block)
            if clean_text != text:
                set_paragraph_text(block, clean_text)
                report["number_prefixes_removed"].append(
                    {"block": idx, "from": text, "to": clean_text}
                )

        if kind == "heading_1":
            ensure_blank_before_paragraph(block)
            current_chapter_no += 1
            current_heading_1 = clean_text
            current_heading_2 = None
            current_heading_3 = None
            normalize_paragraph_to_style(block, STYLE_HEADING_1)
        elif kind == "heading_2":
            current_heading_2 = clean_text
            current_heading_3 = None
            normalize_paragraph_to_style(block, STYLE_HEADING_2)
        elif kind == "heading_3":
            current_heading_3 = clean_text
            normalize_paragraph_to_style(block, STYLE_HEADING_3)
        elif kind == "heading_other":
            normalize_paragraph_to_style(block, STYLE_HEADING_OTHER)
        else:
            normalize_paragraph_to_style(block, STYLE_BODY)

        report["styled"].append(
            {
                "block": idx,
                "type": kind,
                "text": block.text.strip(),
                "reason": reason,
                "confidence": confidence,
            }
        )
        idx += 1

    return report


def build_standard_docx(
    input_docx: Path | str,
    output_docx: Path | str,
    template_docx: Path | str | None = None,
) -> dict[str, Any]:
    """基于 KL 母版把正文文档转换为标准文档。"""
    input_path = Path(input_docx)
    output_path = Path(output_docx)
    template_path = Path(template_docx) if template_docx is not None else DEFAULT_MASTER_TEMPLATE
    if not template_path.exists():
        raise FileNotFoundError(f"KL母版模板不存在: {template_path}")
    source_title = first_nonblank_paragraph_text(input_path)
    has_figures = document_has_figures(input_path)
    has_tables = document_has_tables(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        front_docx = tmp_dir / "front.docx"
        shutil.copy2(template_path, front_docx)

        front_doc = Document(str(front_docx))
        replace_cover_title(front_doc, source_title)
        set_default_headers(front_doc, source_title)
        front_matter = {"template_front_matter_preserved": True}
        front_count = remove_template_sample_body(front_doc)
        front_doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        front_doc.save(str(front_docx))

        master = Document(str(front_docx))
        composer = Composer(master)
        composer.append(Document(str(input_path)))
        composed_docx = tmp_dir / "composed.docx"
        composer.save(str(composed_docx))

        doc = Document(str(composed_docx))
        set_default_headers(doc, source_title)
        report = standardize_appended_body(doc, front_count + 1, source_title)
        doc.save(str(output_path))

    report.update(
        {
            "input": str(input_path),
            "output": str(output_path),
            "template": str(template_path),
            "source_title": source_title,
            "input_has_figures": has_figures,
            "input_has_tables": has_tables,
            "front_matter": front_matter,
            "front_blocks_preserved": front_count,
        }
    )
    return report


def _xml_qn(tag: str) -> str:
    prefix, local = tag.split(":", 1)
    return f"{{{NS[prefix]}}}{local}"


def read_docx_xml(docx: Path | str, name: str) -> str:
    """读取 DOCX 包中的 XML 文件文本。"""
    with zipfile.ZipFile(Path(docx)) as zf:
        try:
            return zf.read(name).decode("utf-8", errors="replace")
        except KeyError:
            return ""


def load_style_names(docx: Path | str) -> dict[str, str]:
    """读取 styles.xml 中 styleId 到样式名称的映射。"""
    styles_xml = read_docx_xml(docx, "word/styles.xml")
    if not styles_xml:
        return {}
    root = ET.fromstring(styles_xml)
    result: dict[str, str] = {}
    for style in root.findall("w:style", NS):
        style_id = style.attrib.get(_xml_qn("w:styleId"))
        name_node = style.find("w:name", NS)
        if not style_id or name_node is None:
            continue
        style_value = name_node.attrib.get(_xml_qn("w:val"))
        if style_value:
            result[style_id] = style_value
    return result


def _paragraph_text_xml(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()


def _paragraph_style_id_xml(p: ET.Element) -> str | None:
    pstyle = p.find("./w:pPr/w:pStyle", NS)
    if pstyle is None:
        return None
    return pstyle.attrib.get(_xml_qn("w:val"))


def _paragraph_field_codes_xml(p: ET.Element) -> list[str]:
    codes = []
    for node in p.findall(".//w:instrText", NS):
        if node.text and node.text.strip():
            codes.append(node.text.strip())
    return codes


def _has_figure_xml(p: ET.Element) -> bool:
    return p.find(".//w:drawing", NS) is not None or p.find(".//w:pict", NS) is not None


def _classify_paragraph_xml(p: ET.Element, style_names: dict[str, str]) -> tuple[str, str, str]:
    text = _paragraph_text_xml(p)
    style_id = _paragraph_style_id_xml(p)
    style_value = style_names.get(style_id or "", style_id or "")
    fields = "\n".join(_paragraph_field_codes_xml(p))

    if "SEQ 图" in fields or CAPTION_TEXT_PATTERNS["figure_caption"].match(text):
        return "figure_caption", "caption field/text matched figure", "high"
    if "SEQ 表" in fields or CAPTION_TEXT_PATTERNS["table_caption"].match(text):
        return "table_caption", "caption field/text matched table", "high"
    if _has_figure_xml(p):
        return "figure", "paragraph contains drawing or pict", "high"
    if style_value in STYLE_TO_TYPE:
        kind, confidence = STYLE_TO_TYPE[style_value]
        return kind, f"matched style {style_value}", confidence
    kind, _cleaned, reason, confidence = classify_heading(text)
    return (
        kind if text else "blank",
        reason if text else "empty paragraph",
        confidence if text else "high",
    )


def _table_dimensions_xml(tbl: ET.Element) -> tuple[int, int]:
    rows = tbl.findall("./w:tr", NS)
    max_cols = 0
    for row in rows:
        max_cols = max(max_cols, len(row.findall("./w:tc", NS)))
    return len(rows), max_cols


def _find_table_caption(blocks: list[BlockReport], table_index: int) -> dict[str, Any] | None:
    before = blocks[table_index - 1] if table_index > 0 else None
    after = blocks[table_index + 1] if table_index + 1 < len(blocks) else None
    if before and before.type == "table_caption":
        return {"position": "above", "block_index": before.index, "text": before.text}
    if after and after.type == "table_caption":
        return {"position": "below", "block_index": after.index, "text": after.text}
    return None


def _find_figure_caption(blocks: list[BlockReport], figure_index: int) -> dict[str, Any] | None:
    before = blocks[figure_index - 1] if figure_index > 0 else None
    after = blocks[figure_index + 1] if figure_index + 1 < len(blocks) else None
    if after and after.type == "figure_caption":
        return {"position": "below", "block_index": after.index, "text": after.text}
    if before and before.type == "figure_caption":
        return {"position": "above", "block_index": before.index, "text": before.text}
    return None


def classify_docx_body(docx: Path | str) -> dict[str, Any]:
    """分类 DOCX 正文结构，返回标题、正文、图、表、题注报告。"""
    docx_path = Path(docx)
    document_xml = read_docx_xml(docx_path, "word/document.xml")
    if not document_xml:
        raise ValueError("word/document.xml not found")

    style_names = load_style_names(docx_path)
    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("document body not found")

    blocks: list[BlockReport] = []
    for child in list(body):
        if child.tag == _xml_qn("w:p"):
            style_id = _paragraph_style_id_xml(child)
            style_value = style_names.get(style_id or "", style_id)
            field_codes = _paragraph_field_codes_xml(child)
            block_type, reason, confidence = _classify_paragraph_xml(child, style_names)
            blocks.append(
                BlockReport(
                    index=len(blocks),
                    kind="paragraph",
                    type=block_type,
                    text=_paragraph_text_xml(child),
                    style_id=style_id,
                    style_name=style_value,
                    reason=reason,
                    confidence=confidence,
                    has_figure=_has_figure_xml(child),
                    field_codes=field_codes or None,
                )
            )
        elif child.tag == _xml_qn("w:tbl"):
            rows, columns = _table_dimensions_xml(child)
            blocks.append(
                BlockReport(
                    index=len(blocks),
                    kind="table",
                    type="table",
                    rows=rows,
                    columns=columns,
                    reason="block is w:tbl",
                    confidence="high",
                )
            )

    for idx, block in enumerate(blocks):
        if block.type == "table":
            block.caption = _find_table_caption(blocks, idx)
        elif block.type == "figure":
            block.caption = _find_figure_caption(blocks, idx)

    summary: dict[str, int] = {}
    for block in blocks:
        summary[block.type] = summary.get(block.type, 0) + 1

    return {
        "source": str(docx_path),
        "summary": summary,
        "blocks": [asdict(block) for block in blocks],
        "headings": [asdict(block) for block in blocks if block.type.startswith("heading_")],
        "figures": [asdict(block) for block in blocks if block.type == "figure"],
        "tables": [asdict(block) for block in blocks if block.type == "table"],
        "captions": [
            asdict(block)
            for block in blocks
            if block.type in {"figure_caption", "table_caption"}
        ],
    }


def write_classification_report(
    docx: Path | str,
    output_json: Path | str,
    *,
    pretty: bool = True,
) -> Path:
    """把 DOCX 分类结果写入 JSON 文件。"""
    output = Path(output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = classify_docx_body(docx)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if pretty else None) + "\n",
        encoding="utf-8",
    )
    return output


def style_names_in_docx(docx: Path | str) -> set[str]:
    """读取文档中定义的样式名称集合。"""
    styles_xml = read_docx_xml(docx, "word/styles.xml")
    if not styles_xml:
        return set()
    root = ET.fromstring(styles_xml)
    names: set[str] = set()
    for style in root.findall("w:style", NS):
        name_node = style.find("w:name", NS)
        if name_node is not None:
            value = name_node.attrib.get(_xml_qn("w:val"))
            if value:
                names.add(value)
    return names


def field_instr_text(docx: Path | str) -> str:
    """读取 document.xml 中所有域代码文本。"""
    document_xml = read_docx_xml(docx, "word/document.xml")
    if not document_xml:
        return ""
    root = ET.fromstring(document_xml)
    parts = [node.text for node in root.findall(".//w:instrText", NS) if node.text]
    return "\n".join(parts)


def check_word_standard(docx: Path | str) -> dict[str, Any]:
    """检查 DOCX 是否包含 KL 标准核心样式和题注/清单字段信号。"""
    docx_path = Path(docx)
    found_styles = style_names_in_docx(docx_path)
    missing_styles = [name for name in REQUIRED_STYLES if name not in found_styles]
    fields = field_instr_text(docx_path)
    missing_fields: list[str] = []
    if ("SEQ 图" in fields or "SEQ 表" in fields) and "STYLEREF KL一级标题" not in fields:
        missing_fields.append("STYLEREF KL一级标题")
    missing_toc = [
        snippet
        for caption, snippet in {
            "SEQ 图": 'TOC \\h \\z \\c "图"',
            "SEQ 表": 'TOC \\h \\z \\c "表"',
        }.items()
        if caption in fields and snippet not in fields
    ]
    return {
        "source": str(docx_path),
        "required_styles_ok": not missing_styles,
        "missing_styles": missing_styles,
        "caption_fields_ok": not missing_fields,
        "missing_field_snippets": missing_fields,
        "figure_table_lists_ok": not missing_toc,
        "missing_toc_snippets": missing_toc,
        "has_wrong_table_toc": 'TOC \\h \\z \\c "表格"' in fields,
        "has_table_seq": "SEQ 表" in fields,
        "has_figure_seq": "SEQ 图" in fields,
    }


__all__ = [
    "STYLE_MAIN_TITLE",
    "STYLE_HEADING_1",
    "STYLE_HEADING_2",
    "STYLE_HEADING_3",
    "STYLE_HEADING_OTHER",
    "STYLE_BODY",
    "STYLE_CAPTION",
    "STYLE_TABLE_HEADER",
    "STYLE_TABLE_BODY",
    "STYLE_IMAGE",
    "PACKAGE_ASSETS_DIR",
    "DEFAULT_MASTER_TEMPLATE",
    "REQUIRED_STYLES",
    "BlockReport",
    "iter_block_items",
    "clean_heading_number",
    "classify_heading",
    "normalize_paragraph_to_style",
    "normalize_table_cell_paragraph",
    "apply_table_styles",
    "add_figure_caption_after",
    "classify_docx_body",
    "write_classification_report",
    "check_word_standard",
    "build_standard_docx",
]
