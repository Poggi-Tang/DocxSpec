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

from docxspec import (
    PartialFieldRefreshError,
    mark_update_fields_on_open,
    normalize_table_list_fields,
    refresh_docx_fields,
    verify_docx_fields,
)
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


def add_simple_field(paragraph, code, cache, *, locked=False):
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), code)
    if locked:
        field.set(qn("w:fldLock"), "true")
    field.append(paragraph.add_run(cache)._r)
    paragraph._p.append(field)


@pytest.mark.parametrize("caption", ["表格", "表"])
def test_table_lists_follow_caption_labels_in_relocated_story(tmp_path, caption):
    path = tmp_path / "captions.docx"
    doc = Document()
    add_simple_field(doc.add_paragraph(), f"SEQ {caption}", "1")
    footer = doc.sections[0].footer.paragraphs[0]
    add_simple_field(footer, r'TOC \h \c "表格"', "Item 1")
    footer.part.partname = PackURI("/word/ds_sections/example/footer.xml")
    doc.save(path)

    assert normalize_table_list_fields(path) == 1
    assert normalize_table_list_fields(path) == 0
    footer = Document(path).sections[0].footer.paragraphs[0]
    assert footer._p.xpath(".//w:fldSimple/@w:instr") == [rf'TOC \h \z \c "{caption}"']


def test_verification_detects_stale_lost_and_locked_results(tmp_path):
    source = tmp_path / "before.docx"
    final = tmp_path / "after.docx"
    doc = Document()
    add_simple_field(doc.add_paragraph(), "REF Bookmark", "999")
    footer = doc.sections[0].footer.paragraphs[0]
    add_simple_field(footer, "PAGE", "1", locked=True)
    add_simple_field(footer, "NUMPAGES", "999")
    doc.save(source)
    doc.paragraphs[0].clear()
    add_simple_field(doc.add_paragraph(), "TOC", "STALE TOC")
    doc.save(final)

    check = verify_docx_fields(final, original=source, page_count=2)
    assert check.fields_checked == 3
    assert any("正文 REF 缺少" in issue for issue in check.issues)
    assert any("页脚 PAGE" in issue and "已锁定" in issue for issue in check.issues)
    assert any("缓存为 999，实际 2 页" in issue for issue in check.issues)
    assert any("正文 TOC" in issue for issue in check.issues)


def test_partial_refresh_retains_input_and_reports_incomplete_result(tmp_path, monkeypatch):
    def incomplete(_source, output):
        doc = Document()
        add_simple_field(doc.add_paragraph(), "REF Bookmark", "Updated")
        doc.save(output)
        return 2

    monkeypatch.setattr("docxspec.word_fields.update_with_libreoffice", incomplete)
    path = tmp_path / "report.docx"
    doc = Document()
    add_simple_field(doc.add_paragraph(), "REF Bookmark", "Original")
    add_simple_field(doc.sections[0].footer.paragraphs[0], "NUMPAGES", "999")
    doc.save(path)
    original = path.read_bytes()

    with pytest.raises(PartialFieldRefreshError, match="NUMPAGES"):
        refresh_docx_fields(path, engine="libreoffice", strict=True)
    assert path.read_bytes() == original
    result = refresh_docx_fields(path, engine="libreoffice")
    assert result.status == "partial"
    assert any("NUMPAGES" in issue for issue in result.issues)
    with ZipFile(path) as archive:
        assert b"Original" in archive.read("word/document.xml")
        assert b"updateFields" in archive.read("word/settings.xml")


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
        "paginate",
        "body",
        "header",
        "next section footer",
        "toc",
        "figures",
        "paginate",
        "toc pages",
        "figures pages",
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
        Fields=Fields(),
        StoryRanges=[header],
        Shapes=[],
        Sections=[section],
        TablesOfContents=[directory],
        TablesOfFigures=[],
        Repaginate=lambda: None,
        ComputeStatistics=lambda _: 1,
    )
    if stabilizes:
        refresh_document_fields(document)
    else:
        with pytest.raises(RuntimeError, match="did not stabilize"):
            refresh_document_fields(document)
    assert passes == ["1", "2", "2" if stabilizes else "3"]


def test_stable_locked_word_field_is_reported_as_unverified():
    fields = Fields()
    fields[0].Locked = True
    fields[0].Code = SimpleNamespace(Text=" PAGE ")
    document = SimpleNamespace(
        Fields=fields,
        StoryRanges=[],
        Shapes=[],
        Sections=[],
        TablesOfContents=[],
        TablesOfFigures=[],
        Repaginate=lambda: None,
        ComputeStatistics=lambda _: 2,
    )
    pages, issues = refresh_document_fields(document)
    assert pages == 2
    assert issues == ("Document: PAGE is locked",)


def test_wps_dispatch_requires_a_new_process(tmp_path, monkeypatch):
    path = tmp_path / "report.docx"
    Document().save(path)
    events = []
    pc = ModuleType("pythoncom")
    pc.CoInitialize = lambda: None
    pc.CoUninitialize = lambda: None
    process = ModuleType("win32process")
    process.EnumProcesses = lambda: [100]
    process.GetWindowThreadProcessId = lambda _: (1, 100)
    doc = SimpleNamespace(
        Fields=Fields(), StoryRanges=[], Shapes=[], Sections=[],
        TablesOfContents=[], TablesOfFigures=[], Repaginate=lambda: None,
        ComputeStatistics=lambda _: 1, Save=lambda: events.append("save"),
        Close=lambda **_: None,
    )
    wps = SimpleNamespace(
        Hwnd=1, Documents=SimpleNamespace(Open=lambda *_, **__: doc),
        Quit=lambda: events.append("quit"),
    )
    client = ModuleType("win32com.client")

    def dispatch(prog_id):
        events.append(prog_id)
        return wps

    client.DispatchEx = dispatch
    win32com = ModuleType("win32com")
    win32com.client = client
    for module in [pc, process, win32com, client]:
        monkeypatch.setitem(sys.modules, module.__name__, module)

    result = refresh_docx_fields(path, engine="wps")
    assert result.status == "failed"
    assert events == ["KWPS.Application"]
    process.GetWindowThreadProcessId = lambda _: (1, 200)
    result = refresh_docx_fields(path, engine="wps", strict=True)
    assert result.status == "refreshed" and result.engine == "wps"
    assert not result.word_refreshed
    assert events[1:] == ["KWPS.Application", "save", "quit"]
