"""Word field refresh helpers."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.oxml import CT_Relationships, parse_xml, serialize_part_xml
from docx.opc.packuri import CONTENT_TYPES_URI, PACKAGE_URI, PackURI
from lxml import etree

from ._word_com import close_word, refresh_document_fields
from ._xml_order import child_in_order

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_QN = f"{{{W_NS}}}"
_UPDATE_FIELDS_SUCCESSORS = (
    "w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat", "w:docVars", "w:rsids",
    "m:mathPr", "w:attachedSchema", "w:themeFontLang", "w:clrSchemeMapping",
    "w:doNotIncludeSubdocsInStats", "w:doNotAutoCompressPictures", "w:forceUpgrade", "w:captions",
    "w:readModeInkLockDown", "w:smartTagType", "sl:schemaLibrary", "w:shapeDefaults",
    "w:doNotEmbedSmartTags", "w:decimalSymbol", "w:listSeparator",
)


@dataclass(frozen=True)
class FieldRefreshResult:
    """Word 域刷新结果。"""

    path: Path
    update_fields_on_open: bool
    table_list_fields_normalized: int
    word_refreshed: bool
    error: str | None = None

    @property
    def status(self) -> str:
        return (
            "failed"
            if self.error
            else ("refreshed" if self.word_refreshed else "marked_for_update")
        )


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
    package_rels = parse_xml(source.read(PACKAGE_URI.rels_uri.membername))
    main_rel = next(
        (rel for rel in package_rels.Relationship_lst if rel.reltype == RT.OFFICE_DOCUMENT), None
    )
    if main_rel is None or main_rel.target_mode != "Internal":
        raise ValueError("DOCX has no internal document part")
    document = PackURI.from_rel_ref(PACKAGE_URI, main_rel.target_ref)
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
    """标记文档在 Word/WPS 打开时自动刷新目录、题注等域。"""

    path = _as_path(docx_path)
    with ZipFile(path) as source:
        updates = _settings_updates(source)
    _rewrite_docx(path, updates)
    return path


def _normalize_table_list_xml(data: bytes) -> tuple[bytes, int]:
    import re

    root = etree.fromstring(data)
    count = 0
    stack = []
    fields = []
    for node in root.iter():
        if node.tag == f"{W_QN}fldSimple":
            fields.append((node, None))
        elif node.tag == f"{W_QN}fldChar":
            kind = node.get(f"{W_QN}fldCharType")
            if kind == "begin":
                stack.append([node, [], False])
            elif kind == "separate" and stack:
                stack[-1][2] = True
            elif kind == "end" and stack:
                owner, nodes, _ = stack.pop()
                fields.append((owner, nodes))
        elif node.tag == f"{W_QN}instrText" and stack and not stack[-1][2]:
            stack[-1][1].append(node)
    for owner, nodes in fields:
        text = (
            owner.get(f"{W_QN}instr", "") if nodes is None else "".join(n.text or "" for n in nodes)
        )
        if not re.match(r"^\s*TOC\b", text, re.I):
            continue
        match = re.search(r'\\c\s+"(表格|表)"', text, re.I)
        if match is None:
            continue
        new = text[: match.start(1)] + "表" + text[match.end(1) :]
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
        xml_parts = [
            name
            for name in src.namelist()
            if name.startswith("word/")
            and name.endswith(".xml")
            and (
                name == "word/document.xml"
                or name.startswith("word/header")
                or name.startswith("word/footer")
            )
        ]
        for name in xml_parts:
            data, count = _normalize_table_list_xml(src.read(name))
            if count:
                updates[name] = data
                normalized += count
    _rewrite_docx(path, updates)
    return normalized


def refresh_fields_with_word(docx_path: str | Path, *, visible: bool = False) -> bool:
    """使用 Microsoft Word COM 立即刷新所有域，适用于 Windows + 已安装 Word。"""

    path = _as_path(docx_path).resolve()
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Refreshing fields with Word requires pywin32.") from exc

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = visible
        word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        doc = word.Documents.Open(str(path), ReadOnly=False, AddToRecentFiles=False)
        refresh_document_fields(doc)
        doc.Save()
        return True
    finally:
        close_word(doc, word, pythoncom.CoUninitialize)


def refresh_docx_fields(
    docx_path: str | Path,
    *,
    use_word: bool = True,
    visible: bool = False,
    normalize_table_list: bool = True,
    raise_on_word_error: bool = False,
) -> FieldRefreshResult:
    """刷新 docx 域。

    该函数先写入打开自动刷新标记，再规范化表目录域；如果 ``use_word`` 为真，
    则尝试通过 Microsoft Word COM 立即刷新域。未安装 Word 或 pywin32 时默认
    不抛异常，而是把错误写入返回结果。
    """

    path = _as_path(docx_path)
    normalized = 0
    mark_update_fields_on_open(path)
    if normalize_table_list:
        normalized += normalize_table_list_fields(path)

    word_refreshed = False
    error: str | None = None
    if use_word:
        try:
            word_refreshed = refresh_fields_with_word(path, visible=visible)
        except Exception as exc:
            error = str(exc)
            if raise_on_word_error:
                raise

    mark_update_fields_on_open(path)

    return FieldRefreshResult(
        path=path,
        update_fields_on_open=True,
        table_list_fields_normalized=normalized,
        word_refreshed=word_refreshed,
        error=error,
    )
