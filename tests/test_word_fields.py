import sys
from types import ModuleType, SimpleNamespace
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from docxspec import normalize_table_list_fields, refresh_docx_fields


def field_doc(path, split=True):
    d = Document()
    d.add_paragraph(r'Example: TOC \h \c "表格"')
    p = d.add_paragraph()
    for kind in ["begin"]:
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), kind)
        p.add_run()._r.append(e)
    for text in ["TOC ", r'\h \c "表格"'] if split else [r'TOC \h \c "表格"']:
        e = OxmlElement("w:instrText")
        e.text = text
        p.add_run()._r.append(e)
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    p.add_run()._r.append(e)
    d.save(path)


@pytest.mark.parametrize("split", [False, True])
def test_only_real_fields_normalized(tmp_path, split):
    p = tmp_path / "a.docx"
    field_doc(p, split)
    assert normalize_table_list_fields(p) == 1
    assert Document(p).paragraphs[0].text == r'Example: TOC \h \c "表格"'
    assert normalize_table_list_fields(p) == 0


def test_marked_is_not_refreshed(tmp_path):
    p = tmp_path / "a.docx"
    field_doc(p)
    result = refresh_docx_fields(p, use_word=False)
    assert result.status == "marked_for_update"
    assert not result.word_refreshed
    with ZipFile(p) as z:
        assert b"updateFields" in z.read("word/settings.xml")


@pytest.mark.parametrize("failure", ["exception", "return_index", "close"])
def test_com_failure_reported_and_cleanup_attempted(tmp_path, monkeypatch, failure):
    p = tmp_path / "a.docx"
    Document().save(p)
    events = []

    def update():
        if failure == "exception":
            raise RuntimeError("update failed")
        return 2 if failure == "return_index" else 0

    def close(**kw):
        events.append("close")
        if failure == "close":
            raise RuntimeError("close failed")

    doc = SimpleNamespace(
        Fields=SimpleNamespace(Update=update),
        StoryRanges=[],
        TablesOfContents=[],
        TablesOfFigures=[],
        Repaginate=lambda: None,
        Save=lambda: events.append("save"),
        Close=close,
    )
    app = SimpleNamespace(
        Documents=SimpleNamespace(Open=lambda *a, **kw: doc), Quit=lambda: events.append("quit")
    )
    pc = ModuleType("pythoncom")
    pc.CoInitialize = lambda: None
    pc.CoUninitialize = lambda: events.append("uninit")
    wc = ModuleType("win32com")
    client = ModuleType("win32com.client")
    client.DispatchEx = lambda *a: app
    wc.client = client
    for name, module in [("pythoncom", pc), ("win32com", wc), ("win32com.client", client)]:
        monkeypatch.setitem(sys.modules, name, module)
    result = refresh_docx_fields(p)
    assert result.status == "failed" and not result.word_refreshed and result.error
    assert "quit" in events and "uninit" in events
    if failure != "close":
        assert "save" not in events
    with pytest.raises(RuntimeError):
        refresh_docx_fields(p, raise_on_word_error=True)


def test_word_refresh_updates_directories_then_repaginated_story_caches(tmp_path, monkeypatch):
    from docxspec import refresh_fields_with_word

    path = tmp_path / "refresh.docx"
    Document().save(path)
    events = []

    def story(label, following=None):
        def update():
            events.append(label)
            return 0
        return SimpleNamespace(Fields=SimpleNamespace(Update=update), NextStoryRange=following)

    def directory(label):
        return SimpleNamespace(
            Update=lambda: events.append(label),
            UpdatePageNumbers=lambda: events.append(label + " pages"),
        )

    doc = SimpleNamespace(
        Fields=story("body").Fields,
        StoryRanges=[story("header", story("next section footer"))],
        TablesOfContents=[directory("toc")],
        TablesOfFigures=[directory("figures")],
        Repaginate=lambda: events.append("paginate"),
        Save=lambda: events.append("save"),
        Close=lambda **kw: events.append("close"),
    )
    app = SimpleNamespace(
        Documents=SimpleNamespace(Open=lambda *args, **kw: doc),
        Quit=lambda: events.append("quit"),
    )
    pc = ModuleType("pythoncom")
    pc.CoInitialize = lambda: None
    pc.CoUninitialize = lambda: events.append("uninit")
    wc = ModuleType("win32com")
    client = ModuleType("win32com.client")
    client.DispatchEx = lambda *args: app
    wc.client = client
    for name, module in [("pythoncom", pc), ("win32com", wc), ("win32com.client", client)]:
        monkeypatch.setitem(sys.modules, name, module)
    assert refresh_fields_with_word(path)
    assert events == [
        "paginate", "body", "header", "next section footer", "toc", "figures",
        "paginate", "header", "next section footer", "toc pages", "figures pages",
        "save", "close", "quit", "uninit",
    ]
