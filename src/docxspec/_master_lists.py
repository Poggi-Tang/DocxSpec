"""Remove empty figure and table list pages from the assembled DS front matter."""

import re

from docx.enum.section import WD_SECTION_START
from docx.oxml.ns import qn
from lxml import etree

from ._field_xml import field_instruction, iter_fields

_PARAGRAPH = qn("w:p")
_SECTION = qn("w:sectPr")
_SECTION_END = f"{qn('w:pPr')}/{_SECTION}"
_PAGE_BEFORE = f"{qn('w:pPr')}/{qn('w:pageBreakBefore')}"
_LIST_TITLES = {
    "图录": {"图", "figure"},
    "图目录": {"图", "figure"},
    "插图清单": {"图", "figure"},
    "表录": {"表", "表格", "table"},
    "表目录": {"表", "表格", "table"},
    "表格清单": {"表", "表格", "table"},
}
FIGURE_CAPTION_LABELS = {"图", "figure"}
TABLE_CAPTION_LABELS = {"表", "表格", "table"}
_TOC = re.compile(r"^\s*TOC\b", re.IGNORECASE)
_LIST_SWITCH = re.compile(r'(?:^|\s)\\c\s+(?:"([^"]+)"|([^\s\\]+))', re.IGNORECASE)
_SEQ = re.compile(r'^\s*SEQ\s+(?:"([^"]+)"|([^\s\\]+))', re.IGNORECASE)
_REPEAT_SEQ = re.compile(r"(?:^|\s)\\c(?:\s|$)", re.IGNORECASE)
_MEANINGFUL = {qn(tag) for tag in ("w:tbl", "w:drawing", "w:pict", "w:object")}
_PICTURES = {qn("a:blip"), qn("v:imagedata")}


def _text(element):
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def _substantive(element):
    return bool(_text(element).strip()) or next(element.iter(*_MEANINGFUL), None) is not None


def _page_break(element):
    return any(node.get(qn("w:type")) == "page" for node in element.iter(qn("w:br")))


def _standalone_page_break(element):
    return element.tag == _PARAGRAPH and not _substantive(element) and _page_break(element)


def _pages(elements):
    """Split at dedicated page separators, keeping trailing separators with their page."""
    page = []
    for element in elements:
        before = element.find(_PAGE_BEFORE)
        if page and before is not None and before.get(qn("w:val")) not in ("0", "false", "off"):
            yield page
            page = []
        page.append(element)
        if element.find(_SECTION_END) is not None or _standalone_page_break(element):
            yield page
            page = []
    if page:
        yield page


def _first_title(page):
    for element in page:
        for paragraph in element.iter(_PARAGRAPH):
            text = "".join(_text(paragraph).split())
            if text:
                return paragraph, text
    return None, ""


def _body_block(node, body):
    while node.getparent() is not body:
        node = node.getparent()
    return node


def _has_content_outside_list(page, heading, opening, closing):
    inside_heading = inside_field = False
    for element in page:
        for event, node in etree.iterwalk(element, events=("start", "end")):
            if node is heading:
                inside_heading = event == "start"
            if node is opening and event == "start":
                inside_field = True
            if node is closing and event == "end":
                inside_field = False
            if (
                event == "start"
                and not (inside_heading or inside_field)
                and (
                    node.tag in _MEANINGFUL or (node.tag == qn("w:t") and (node.text or "").strip())
                )
            ):
                return True
    return False


def caption_labels(elements):
    labels = set()
    previous_figures = set()
    previous_picture = False
    for element in elements:
        sequences = set()
        for owner, _, runs in iter_fields(element):
            code = field_instruction(owner, runs)
            match = _SEQ.match(code)
            if match and not _REPEAT_SEQ.search(code[match.end() :]):
                sequences.add((match[1] or match[2]).casefold())
        labels.update(sequences & TABLE_CAPTION_LABELS)
        figures = sequences & FIGURE_CAPTION_LABELS
        picture = next(element.iter(*_PICTURES), None) is not None
        if picture:
            labels.update(previous_figures | figures)
        if previous_picture:
            labels.update(figures)
        if picture or sequences or _substantive(element):
            previous_figures = figures
            previous_picture = picture
    return labels


def list_field_label(code):
    match = _LIST_SWITCH.search(code) if _TOC.match(code) else None
    return (match[1] or match[2]).casefold() if match else None


def prune_caption_list_pages(body):
    """Remove only dedicated list pages after the main TOC, using final body captions."""
    pages = list(_pages(element for element in body if element.tag != _SECTION))
    # Native Word directory fields can begin and end in different paragraphs.
    toc_fields = [
        (_body_block(owner, body), _body_block(end, body), owner, end, code)
        for owner, end, runs in iter_fields(body)
        if _TOC.match(code := field_instruction(owner, runs))
    ]
    optional = []
    after_toc = False
    for i, page in enumerate(pages):
        heading, title = _first_title(page)
        if not after_toc and title != "目录":
            continue
        blocks = set(page)
        fields = [
            (owner, end, code)
            for start_block, end_block, owner, end, code in toc_fields
            if start_block in blocks and end_block in blocks
        ]
        if not after_toc:
            after_toc = any(not _LIST_SWITCH.search(code) for _, _, code in fields)
            continue

        accepted = _LIST_TITLES.get(title)
        if not accepted or len(fields) != 1:
            break
        opening, closing, code = fields[0]
        label = list_field_label(code)
        if label not in accepted or _has_content_outside_list(page, heading, opening, closing):
            break
        optional.append((i, page, label))

    if not optional:
        return []
    first_body_page = optional[-1][0] + 1
    body_labels = caption_labels(element for page in pages[first_body_page:] for element in page)
    removed = []
    for _, page, label in optional:
        if label not in body_labels:
            for element in page:
                body.remove(element)
                removed.append(element)
    return removed


def has_body_page_start(document):
    """Check for a separator already present before the appended body."""
    for element in reversed(document.element.body):
        if element.tag == _SECTION:
            continue
        if _standalone_page_break(element):
            return True
        if element.find(_SECTION_END) is not None:
            return document.sections[-1].start_type not in (
                WD_SECTION_START.CONTINUOUS,
                WD_SECTION_START.NEW_COLUMN,
            )
        if _substantive(element):
            break
    return False
