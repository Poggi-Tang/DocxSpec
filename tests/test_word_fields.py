import sys
from types import ModuleType, SimpleNamespace
from zipfile import ZipFile

import pytest
from docx import Document
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from docxspec import mark_update_fields_on_open, normalize_table_list_fields, refresh_docx_fields
from docxspec._word_com import refresh_document_fields


class Fields(list):
    def __init__(self, update=lambda: 0):
        super().__init__([SimpleNamespace(Result=SimpleNamespace(Text="cache"))])
        self.Update = update


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


def test_mark_creates_reachable_settings_part_when_missing(tmp_path):
    path = tmp_path / "without-settings.docx"
    doc = Document()
    settings_id = next(key for key, rel in doc.part.rels.items() if rel.reltype == RT.SETTINGS)
    doc.part.drop_rel(settings_id)
    doc.save(path)
    with ZipFile(path) as package:
        assert "word/settings.xml" not in package.namelist()
        before = package.read("word/document.xml")
    mark_update_fields_on_open(path)
    settings = Document(path).part.part_related_by(RT.SETTINGS)
    assert settings.content_type == CT.WML_SETTINGS
    assert settings.element.find(qn("w:updateFields")).get(qn("w:val")) == "true"
    with ZipFile(path) as package:
        assert package.read("word/document.xml") == before


def test_mark_fixes_legacy_order_in_relocated_settings_and_is_idempotent(tmp_path):
    path = tmp_path / "relocated-settings.docx"
    doc = Document()
    settings = doc.part.part_related_by(RT.SETTINGS)
    settings.partname = PackURI("/word/config/report.xml")
    for _ in range(2):
        settings.element.append(OxmlElement("w:updateFields"))
    doc.save(path)
    mark_update_fields_on_open(path)
    first = path.read_bytes()
    mark_update_fields_on_open(path)
    assert path.read_bytes() == first
    with ZipFile(path) as package:
        assert "word/settings.xml" not in package.namelist()
        settings = etree.fromstring(package.read("word/config/report.xml"))
    update = settings.findall(qn("w:updateFields"))
    assert len(update) == 1
    assert settings.index(update[0]) < settings.index(settings.find(qn("w:compat")))


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
        Fields=Fields(update),
        StoryRanges=[],
        Shapes=[],
        Sections=[],
        TablesOfContents=[],
        TablesOfFigures=[],
        ComputeStatistics=lambda _: 1,
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


def test_word_refresh_updates_directories_and_every_story_until_stable(tmp_path, monkeypatch):
    from docxspec import refresh_fields_with_word

    path = tmp_path / "refresh.docx"
    Document().save(path)
    events = []

    def story(label, following=None):
        def update():
            events.append(label)
            return 0
        return SimpleNamespace(StoryType=7, Fields=Fields(update), NextStoryRange=following)

    def directory(label):
        return SimpleNamespace(
            Update=lambda: events.append(label),
            UpdatePageNumbers=lambda: events.append(label + " pages"),
            Range=SimpleNamespace(Text=label),
        )

    doc = SimpleNamespace(
        Fields=story("body").Fields,
        StoryRanges=[story("header", story("next section footer"))],
        Shapes=[],
        Sections=[],
        TablesOfContents=[directory("toc")],
        TablesOfFigures=[directory("figures")],
        Repaginate=lambda: events.append("paginate"),
        ComputeStatistics=lambda _: 1,
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
        "paginate", "toc pages", "figures pages",
    ] * 2 + ["save", "close", "quit", "uninit"]


@pytest.mark.parametrize("area", ["linked_footer", "grouped_text_box", "directory"])
@pytest.mark.parametrize("stabilizes", [True, False])
def test_word_field_stability_requires_matching_non_body_results(area, stabilizes):
    footer_fields = Fields()
    box_fields = Fields()
    directory = SimpleNamespace(Update=lambda: None, Range=SimpleNamespace(Text="toc"))
    values = iter(["1", "2", "2" if stabilizes else "3"])
    passes = []

    def update(result):
        result.Text = next(values)
        passes.append(result.Text)
        return 0

    directory.UpdatePageNumbers = lambda: None
    if area == "linked_footer":
        footer_fields.Update = lambda: update(footer_fields[0].Result)
    elif area == "grouped_text_box":
        box_fields.Update = lambda: update(box_fields[0].Result)
    else:
        directory.UpdatePageNumbers = lambda: update(directory.Range)

    box = SimpleNamespace(
        Type=17,
        TextFrame=SimpleNamespace(HasText=True, TextRange=SimpleNamespace(Fields=box_fields)),
    )
    group = SimpleNamespace(Type=6, GroupItems=[box])
    section = SimpleNamespace(Headers=[], Footers=[SimpleNamespace(Shapes=[group])])
    footer = SimpleNamespace(StoryType=9, Fields=footer_fields, NextStoryRange=None)
    header = SimpleNamespace(StoryType=7, Fields=Fields(), NextStoryRange=footer)
    document = SimpleNamespace(
        Fields=Fields(), StoryRanges=[header], Shapes=[], Sections=[section],
        TablesOfContents=[directory], TablesOfFigures=[], Repaginate=lambda: None,
        ComputeStatistics=lambda _: 1,
    )
    if stabilizes:
        refresh_document_fields(document)
    else:
        with pytest.raises(RuntimeError, match="did not stabilize"):
            refresh_document_fields(document)
    assert passes == ["1", "2", "2" if stabilizes else "3"]
