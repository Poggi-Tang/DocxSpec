"""Word field refresh helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_QN = f"{{{W_NS}}}"


@dataclass(frozen=True)
class FieldRefreshResult:
    """Word 域刷新结果。"""

    path: Path
    update_fields_on_open: bool
    table_list_fields_normalized: int
    word_refreshed: bool
    error: str | None = None


def _as_path(docx_path: str | Path) -> Path:
    path = Path(docx_path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Only .docx files are supported: {path}")
    return path


def _rewrite_docx(
    path: Path,
    transforms: dict[str, Callable[[bytes], bytes]],
) -> None:
    """重写 docx 包内指定 XML 部件，其他文件原样复制。"""

    with ZipFile(path, "r") as src:
        names = set(src.namelist())
        entries = [(info, src.read(info.filename)) for info in src.infolist()]

    with NamedTemporaryFile(delete=False, suffix=".docx", dir=path.parent) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        with ZipFile(tmp_path, "w", ZIP_DEFLATED) as dst:
            for info, data in entries:
                transform = transforms.get(info.filename)
                if transform is not None:
                    data = transform(data)
                dst.writestr(info, data)
            if "word/settings.xml" not in names and "word/settings.xml" in transforms:
                dst.writestr("word/settings.xml", transforms["word/settings.xml"](b""))
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _mark_settings_xml(data: bytes) -> bytes:
    if data:
        root = etree.fromstring(data)
    else:
        root = etree.Element(f"{W_QN}settings", nsmap={"w": W_NS})

    update_fields = root.find(f"{W_QN}updateFields")
    if update_fields is None:
        update_fields = etree.Element(f"{W_QN}updateFields")
        root.append(update_fields)
    update_fields.set(f"{W_QN}val", "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def mark_update_fields_on_open(docx_path: str | Path) -> Path:
    """标记文档在 Word/WPS 打开时自动刷新目录、题注等域。"""

    path = _as_path(docx_path)
    _rewrite_docx(path, {"word/settings.xml": _mark_settings_xml})
    return path


def _normalize_table_list_xml(data: bytes) -> tuple[bytes, int]:
    text = data.decode("utf-8")
    count = 0
    replacements = {
        r'TOC \h \c "表"': r'TOC \h \z \c "表"',
        r'TOC \h \c "表格"': r'TOC \h \z \c "表"',
        r'TOC \h \z \c "表格"': r'TOC \h \z \c "表"',
        r"TOC \h \c &quot;表&quot;": r"TOC \h \z \c &quot;表&quot;",
        r"TOC \h \c &quot;表格&quot;": r"TOC \h \z \c &quot;表&quot;",
        r"TOC \h \z \c &quot;表格&quot;": r"TOC \h \z \c &quot;表&quot;",
    }
    for old, new in replacements.items():
        occurrences = text.count(old)
        if occurrences:
            text = text.replace(old, new)
            count += occurrences
    return text.encode("utf-8"), count


def normalize_table_list_fields(docx_path: str | Path) -> int:
    """把表目录域统一为 Word/WPS 可识别的 ``TOC \\h \\z \\c "表"``。"""

    path = _as_path(docx_path)
    normalized = 0

    def transform(data: bytes) -> bytes:
        nonlocal normalized
        new_data, count = _normalize_table_list_xml(data)
        normalized += count
        return new_data

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
    _rewrite_docx(path, {name: transform for name in xml_parts})
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
        doc = word.Documents.Open(str(path), ReadOnly=False, AddToRecentFiles=False)

        try:
            doc.Fields.Update()
        except Exception:
            pass

        for story in doc.StoryRanges:
            current = story
            while current is not None:
                try:
                    current.Fields.Update()
                except Exception:
                    pass
                try:
                    current = current.NextStoryRange
                except Exception:
                    current = None

        for toc in doc.TablesOfContents:
            toc.Update()
        for tof in doc.TablesOfFigures:
            tof.Update()

        doc.Save()
        return True
    finally:
        if doc is not None:
            doc.Close(SaveChanges=False)
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()


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

    if normalize_table_list:
        normalized += normalize_table_list_fields(path)
    mark_update_fields_on_open(path)

    return FieldRefreshResult(
        path=path,
        update_fields_on_open=True,
        table_list_fields_normalized=normalized,
        word_refreshed=word_refreshed,
        error=error,
    )
