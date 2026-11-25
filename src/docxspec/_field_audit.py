"""Inspect persisted results separately from Office's on-screen pagination."""

import re
from collections import Counter
from dataclasses import dataclass
from zipfile import ZipFile

from docx.oxml.ns import qn
from lxml import etree

from ._field_xml import iter_field_results, story_parts

_TRACKED = {"TOC", "SEQ", "STYLEREF", "REF", "PAGEREF", "PAGE", "NUMPAGES", "SECTIONPAGES"}
_ON = {"1", "true", "on"}
_UNRESOLVED = re.compile(
    r"^(?:STALE TOC|目录待目标 Office 刷新|Error!|错误[!！]|#REF!)", re.IGNORECASE
)


@dataclass(frozen=True)
class FieldVerification:
    fields_checked: int
    issues: tuple[str, ...]


def _saved_results(path):
    with ZipFile(path) as package:
        for name, area in story_parts(package, active_only=True):
            if name not in package.namelist():
                raise ValueError(f"Missing DOCX story: {name}")
            root = etree.fromstring(package.read(name))
            for owner, code, text in iter_field_results(root):
                words = code.split(None, 1)
                kind = words[0].upper() if words else ""
                if kind in _TRACKED:
                    box = next(owner.iterancestors(qn("w:txbxContent")), None)
                    location = area + "文本框" if box is not None else area
                    yield (
                        location,
                        name,
                        kind,
                        text.strip(),
                        owner.get(qn("w:fldLock")) in _ON,
                        owner.get(qn("w:dirty")) in _ON,
                    )


def verify_docx_fields(path, *, original=None, page_count=None):
    """Inspect saved caches and optionally check preservation against a source DOCX."""
    saved = list(_saved_results(path))
    issues = []
    if original is not None:
        previous = list(_saved_results(original))
        before = Counter((area, kind) for area, _, kind, *_ in previous)
        after = Counter((area, kind) for area, _, kind, *_ in saved)
        for (area, kind), count in (before - after).items():
            issues.append(f"{area} {kind} 缺少 {count} 个域")
        if sum(locked for _, _, _, _, locked, _ in saved) < sum(
            locked for _, _, _, _, locked, _ in previous
        ):
            issues.append("部分锁定域在重新保存后丢失或变为未锁定")
    for area, part, kind, text, locked, dirty in saved:
        label = f"{area} {kind} ({part})"
        if locked:
            issues.append(f"{label} 已锁定")
        elif not text or _UNRESOLVED.match(text):
            # Bookmark text can intentionally be empty. Other tracked fields
            # have a visible result when resolved.
            if text or kind != "REF":
                issues.append(f"{label} 没有有效的已保存结果")
        elif kind == "NUMPAGES" and page_count is not None and text.isdecimal():
            if int(text) != page_count:
                issues.append(f"{label} 缓存为 {text}，实际 {page_count} 页")
        elif kind == "SECTIONPAGES" and page_count is not None and text.isdecimal():
            if not 1 <= int(text) <= page_count:
                issues.append(f"{label} 缓存为 {text}，文档共 {page_count} 页")
        elif dirty:
            issues.append(f"{label} 仍被标记为待更新")
    return FieldVerification(len(saved), tuple(dict.fromkeys(issues)))
