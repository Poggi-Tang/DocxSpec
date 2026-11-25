"""Word field refresh helpers."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.oxml import CT_Relationships, parse_xml, serialize_part_xml
from docx.opc.packuri import CONTENT_TYPES_URI, PackURI
from lxml import etree

from ._field_audit import verify_docx_fields
from ._field_xml import document_part_uri, field_instruction, iter_fields, story_parts
from ._libreoffice_fields import update_with_libreoffice
from ._master_lists import TABLE_CAPTION_ALIASES, prune_caption_list_pages, sequence_label
from ._staged_output import staged_output
from ._word_com import COM_PROG_IDS, close_word, refresh_document_fields
from ._xml_order import child_in_order

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_QN = f"{{{W_NS}}}"
_UPDATE_FIELDS_SUCCESSORS = (
    "w:hdrShapeDefaults",
    "w:footnotePr",
    "w:endnotePr",
    "w:compat",
    "w:docVars",
    "w:rsids",
    "m:mathPr",
    "w:attachedSchema",
    "w:themeFontLang",
    "w:clrSchemeMapping",
    "w:doNotIncludeSubdocsInStats",
    "w:doNotAutoCompressPictures",
    "w:forceUpgrade",
    "w:captions",
    "w:readModeInkLockDown",
    "w:smartTagType",
    "sl:schemaLibrary",
    "w:shapeDefaults",
    "w:doNotEmbedSmartTags",
    "w:decimalSymbol",
    "w:listSeparator",
)


@dataclass(frozen=True)
class FieldRefreshResult:
    """Word 域刷新结果。"""

    path: Path
    update_fields_on_open: bool
    table_list_fields_normalized: int
    word_refreshed: bool
    error: str | None = None
    engine: str | None = None
    issues: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.error:
            return "failed"
        if self.issues:
            return "partial"
        return (
            "refreshed"
            if self.word_refreshed or self.engine in {"libreoffice", "wps"}
            else "marked_for_update"
        )


class PartialFieldRefreshError(RuntimeError):
    """An Office run left some fields unverified in the saved DOCX."""

    def __init__(self, issues: tuple[str, ...]):
        self.issues = issues
        super().__init__("域未完整更新：" + "；".join(issues))


def _as_path(docx_path: str | Path) -> Path:
    path = Path(docx_path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Only .docx files are supported: {path}")
    return path


def _rewrite_docx(path: Path, updates: dict[str, bytes]) -> None:
    """重写 docx 包内指定 XML 部件，其他文件原样复制。"""
    if not updates:
        return
    with NamedTemporaryFile(delete=False, suffix=".docx", dir=path.parent) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        with ZipFile(path) as src, ZipFile(tmp_path, "w", ZIP_DEFLATED) as dst:
            dst.comment = src.comment
            for info in src.infolist():
                data = updates.get(info.filename)
                if data is None:
                    data = src.read(info)
                dst.writestr(info, data)
            names = set(src.namelist())
            for name, data in updates.items():
                if name not in names:
                    dst.writestr(name, data)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _mark_settings_xml(data: bytes) -> bytes:
    if data:
        root = etree.fromstring(data)
    else:
        root = etree.Element(f"{W_QN}settings", nsmap={"w": W_NS})

    if root.tag != f"{W_QN}settings":
        raise ValueError("Invalid Word settings part")
    for duplicate in root.findall(f"{W_QN}updateFields")[1:]:
        root.remove(duplicate)
    update_fields = child_in_order(root, "w:updateFields", _UPDATE_FIELDS_SUCCESSORS)
    update_fields.set(f"{W_QN}val", "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _settings_updates(source: ZipFile) -> dict[str, bytes]:
    document = document_part_uri(source)
    rels_name = document.rels_uri.membername
    names = set(source.namelist())
    rels = parse_xml(source.read(rels_name)) if rels_name in names else CT_Relationships.new()
    settings_rel = next((rel for rel in rels.Relationship_lst if rel.reltype == RT.SETTINGS), None)
    updates = {}
    if settings_rel is not None:
        if settings_rel.target_mode != "Internal":
            raise ValueError("DOCX settings must be an internal part")
        settings = PackURI.from_rel_ref(document.baseURI, settings_rel.target_ref)
    else:
        settings = PackURI.from_rel_ref(document.baseURI, "settings.xml")
        if settings.membername in names:
            try:
                orphan = etree.fromstring(source.read(settings.membername))
            except etree.XMLSyntaxError:
                orphan = None
            if orphan is None or orphan.tag != f"{W_QN}settings":
                for number in count(1):
                    settings = PackURI.from_rel_ref(document.baseURI, f"settings{number}.xml")
                    if settings.membername not in names:
                        break
        ids = {rel.rId for rel in rels.Relationship_lst}
        rel_id = next(f"rId{i}" for i in count(1) if f"rId{i}" not in ids)
        rels.add_rel(rel_id, RT.SETTINGS, settings.relative_ref(document.baseURI))
        updates[rels_name] = rels.xml

    content_types = parse_xml(source.read(CONTENT_TYPES_URI.membername))
    override = next((item for item in content_types.overrides if item.partname == settings), None)
    if override is None:
        content_types.add_override(settings, CT.WML_SETTINGS)
        updates[CONTENT_TYPES_URI.membername] = serialize_part_xml(content_types)
    elif override.get("ContentType") != CT.WML_SETTINGS:
        override.set("ContentType", CT.WML_SETTINGS)
        updates[CONTENT_TYPES_URI.membername] = serialize_part_xml(content_types)

    settings_name = settings.membername
    original = source.read(settings_name) if settings_name in names else b""
    marked = _mark_settings_xml(original)
    if marked != original:
        updates[settings_name] = marked
    return updates


def mark_update_fields_on_open(docx_path: str | Path) -> Path:
    """请求目标 Office 打开文档时更新域。"""

    path = _as_path(docx_path)
    with ZipFile(path) as source:
        updates = _settings_updates(source)
    _rewrite_docx(path, updates)
    return path


def prune_empty_caption_lists(docx_path: str | Path) -> Path:
    """Remove empty DS front-matter lists from an already assembled report."""
    path = _as_path(docx_path)
    with ZipFile(path) as source:
        name = document_part_uri(source).membername
        document = etree.fromstring(source.read(name))
    body = document.find(f"{W_QN}body")
    if body is not None and prune_caption_list_pages(body):
        _rewrite_docx(path, {name: serialize_part_xml(document)})
    return path


def _normalize_table_list_xml(data: bytes, labels: set[str]) -> tuple[bytes, int]:
    root = etree.fromstring(data)
    count = 0
    for owner, _, nodes in iter_fields(root):
        text = field_instruction(owner, nodes)
        if not re.match(r"^\s*TOC\b", text, re.I):
            continue
        match = re.search(r'\\c\s+(?:"(表格|表)"|(表格|表)(?=\s|$))', text, re.I)
        if match is None:
            continue
        group = 1 if match[1] is not None else 2
        label = match[group]
        target = label if label in labels else "表格" if "表格" in labels else "表"
        new = text[: match.start(group)] + target + text[match.end(group) :]
        if not re.search(r"\\z(?=\s|$)", new, re.I):
            new = new[: match.start()] + r"\z " + new[match.start() :]
        if new == text:
            continue
        if nodes is None:
            owner.set(f"{W_QN}instr", new)
        elif nodes:
            nodes[0].text = new
            for node in nodes[1:]:
                node.text = ""
        owner.set(f"{W_QN}dirty", "true")
        count += 1
    return (
        (etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), count)
        if count
        else (data, 0)
    )


def normalize_table_list_fields(docx_path: str | Path) -> int:
    """把表目录域统一为 Word/WPS 可识别的 ``TOC \\h \\z \\c "表"``。"""

    path = _as_path(docx_path)
    normalized = 0
    updates = {}
    with ZipFile(path, "r") as src:
        main = etree.fromstring(src.read(document_part_uri(src).membername))
        labels = {
            sequence_label(field_instruction(owner, runs)) for owner, _, runs in iter_fields(main)
        } & TABLE_CAPTION_ALIASES
        for name, _ in story_parts(src):
            data, count = _normalize_table_list_xml(src.read(name), labels)
            if count:
                updates[name] = data
                normalized += count
    _rewrite_docx(path, updates)
    return normalized


def _update_with_com(path: Path, visible: bool, engine: str) -> tuple[int, tuple[str, ...]]:
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("使用 Word 或 WPS 自动化刷域需要 pywin32") from exc

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        if engine == "wps":
            import win32process  # type: ignore[import-not-found]

            existing = set(win32process.EnumProcesses())
            instance = win32com.client.DispatchEx(COM_PROG_IDS[engine])
            pid = win32process.GetWindowThreadProcessId(instance.Hwnd)[1]
            if not pid or pid in existing:
                raise RuntimeError("无法确认 WPS 启动了独立实例，已停止刷域")
            word = instance
        else:
            word = win32com.client.DispatchEx(COM_PROG_IDS[engine])
        word.Visible = visible
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        doc = word.Documents.Open(str(path), ReadOnly=False, AddToRecentFiles=False)
        pages, issues = refresh_document_fields(doc)
        doc.Save()
        return pages, issues
    finally:
        close_word(doc, word, pythoncom.CoUninitialize)


def refresh_fields_with_word(docx_path: str | Path, *, visible: bool = False) -> bool:
    """Refresh with Microsoft Word and verify field caches after it closes the file."""
    _refresh_verified_com(_as_path(docx_path).resolve(), visible, "word")
    return True


def _refresh_verified_com(path: Path, visible: bool, engine: str) -> None:
    with TemporaryDirectory(prefix="docxspec-fields-", dir=path.parent) as folder:
        staged = Path(folder) / path.name
        shutil.copy2(path, staged)
        pages, issues = _update_with_com(staged, visible, engine)
        inspection = verify_docx_fields(staged, original=path, page_count=pages)
        if issues or inspection.issues:
            raise PartialFieldRefreshError(issues + inspection.issues)
        staged.replace(path)


def refresh_docx_fields(
    docx_path: str | Path,
    *,
    use_word: bool = True,
    visible: bool = False,
    normalize_table_list: bool = True,
    raise_on_word_error: bool = False,
    engine: str | None = None,
    strict: bool = False,
) -> FieldRefreshResult:
    """Prepare fields or refresh and verify with an explicitly selected Office engine."""

    path = _as_path(docx_path)
    engine = engine if engine is not None else ("word" if use_word else "mark")
    if engine not in {"mark", "word", "wps", "libreoffice"}:
        raise ValueError(f"未知刷域引擎：{engine}")
    word_refreshed = False
    error: str | None = None
    issues: tuple[str, ...] = ()
    required = strict or (engine == "word" and raise_on_word_error)
    with staged_output(path) as prepared:
        shutil.copy2(path, prepared)
        mark_update_fields_on_open(prepared)
        normalized = normalize_table_list_fields(prepared) if normalize_table_list else 0
        if engine != "mark":
            try:
                if engine == "word":
                    word_refreshed = refresh_fields_with_word(prepared, visible=visible)
                elif engine == "wps":
                    _refresh_verified_com(prepared.resolve(), visible, engine)
                else:
                    with staged_output(prepared) as updated:
                        pages = update_with_libreoffice(prepared, updated)
                        inspection = verify_docx_fields(
                            updated, original=prepared, page_count=pages
                        )
                        if inspection.issues:
                            raise PartialFieldRefreshError(inspection.issues)
            except PartialFieldRefreshError as exc:
                issues = exc.issues
                if required:
                    raise
            except Exception as exc:
                error = str(exc)
                if required:
                    raise
            else:
                mark_update_fields_on_open(prepared)

    return FieldRefreshResult(
        path=path,
        update_fields_on_open=True,
        table_list_fields_normalized=normalized,
        word_refreshed=word_refreshed,
        error=error,
        engine=engine if engine != "mark" else None,
        issues=issues,
    )
