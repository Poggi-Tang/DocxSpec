from itertools import product
from pathlib import Path

import pytest
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image

from docxspec import (
    DEFAULT_DS_SECTIONS,
    DEFAULT_MASTER_TEMPLATE,
    WordAPI,
    build_standard_docx,
    check_word_standard,
    prune_empty_caption_lists,
)
from docxspec.kl_standard import field_instr_text, remove_template_sample_body


@pytest.fixture
def picture(tmp_path):
    path = tmp_path / "fixture.png"
    Image.new("RGB", (100, 60), "navy").save(path)
    return str(path)


@pytest.fixture
def blank_master(tmp_path):
    master = Document(DEFAULT_MASTER_TEMPLATE)
    remove_template_sample_body(master)
    path = tmp_path / "blank-master.docx"
    master.add_paragraph("{{p content}}")
    master.save(path)
    return path


def assert_master_lists(path, *, figure, table, legacy=False):
    document = Document(path)
    headings = {"".join(paragraph.text.split()) for paragraph in document.paragraphs}
    instructions = field_instr_text(path)
    assert ("图录" in headings) == figure
    assert ("表录" in headings) == table
    assert ('TOC \\h \\z \\c "图"' in instructions) == figure
    assert ('TOC \\h \\z \\c "表"' in instructions) == table
    assert 'TOC \\o "1-7"' in instructions
    assert any("文件编号" in p.text for p in document.paragraphs)
    assert document.tables[1].rows[0].cells[1].text == "版本号"
    assert len(document.sections) == 4 + figure + table
    breaks = document.element.body.xpath('.//w:br[@w:type="page"]')
    if legacy:
        # The legacy master has a hard break after the cover only.
        (cover_break,) = breaks
        paragraph = next(cover_break.iterancestors(qn("w:p")))
        assert document.element.body.index(paragraph) < document.element.body.index(
            document.tables[1]._tbl
        )
    else:
        assert not breaks
        assert document.settings.element.xpath('./w:updateFields[@w:val="true"]')
        assert next(p for p in document.paragraphs if "文件编号" in p.text).style.name == "DS正文"
        assert all(section.start_type == WD_SECTION_START.NEW_PAGE for section in document.sections)
        numbering = [section._sectPr.find(qn("w:pgNumType")) for section in document.sections[2:]]
        assert [number.get(qn("w:fmt")) for number in numbering] == [
            *["upperRoman"] * (1 + figure + table),
            "decimal",
        ]
        assert [number.get(qn("w:start")) for number in numbering] == [
            "1",
            *[None] * (figure + table),
            "1",
        ]


@pytest.mark.parametrize(("figure", "table"), list(product((False, True), repeat=2)))
def test_standard_document_uses_captions_added_during_final_assembly(
    tmp_path, picture, figure, table
):
    input_docx = tmp_path / "body.docx"
    output = tmp_path / "report.docx"
    source = Document()
    source.add_heading("正文验收", level=1)
    source.add_paragraph("验证结果。")
    if figure:
        source.add_picture(picture)
    if table:
        source.add_table(rows=1, cols=1).cell(0, 0).text = "通过"
    source.save(input_docx)

    build_result = build_standard_docx(input_docx, output)

    assert bool(build_result["figure_captions_added"]) == figure
    assert bool(build_result["table_captions_added"]) == table
    assert_master_lists(output, figure=figure, table=table)
    assert check_word_standard(output)["figure_table_lists_ok"]


def test_each_render_uses_its_captions_and_keeps_the_reusable_template(
    tmp_path,
    blank_master,
    picture,
):
    api = WordAPI(str(blank_master))
    original = blank_master.read_bytes()
    for figure, table in product((False, True), repeat=2):
        output = tmp_path / f"report-{figure}-{table}.docx"
        body = api.new_container()
        body.add_heading("正文验收", level=1)
        # The picture and table are always present, but only the fields create list entries.
        body.add_image(picture)
        if figure:
            body.add_figure_caption_auto("有效图题注")
        else:
            body.add_paragraph("图 1-1 仅展示文字")
        body.add_table([[{"text": "结果"}, {"text": "通过"}]])
        if table:
            body.add_table_caption_auto("有效表题注")
        api.render({"content": body.subdoc}, output)
        assert_master_lists(output, figure=figure, table=table, legacy=True)
        assert len(Document(output).inline_shapes) >= 1
    assert blank_master.read_bytes() == original


def test_custom_cover_uses_ds_styles_and_preserves_its_header_and_footer(tmp_path, picture):
    custom = tmp_path / "front"
    custom.mkdir()
    cover = Document(DEFAULT_DS_SECTIONS / "cover.docx")
    cover.styles["DS主标题"].font.name = "Different font"
    cover.add_paragraph("独立编辑的封面", style="DS主标题")
    header = cover.sections[0].header.paragraphs[0]
    header.text = "自定义封面页眉"
    header.add_run().add_picture(picture)
    cover.sections[0].footer.paragraphs[0].text = "自定义封面页脚"
    cover_path = custom / "cover.docx"
    cover.save(cover_path)
    original = cover_path.read_bytes()
    for name in ("figures", "tables"):
        (custom / f"{name}.docx").write_bytes(b"unused; should never be opened")

    source = Document()
    source.add_paragraph("报告标题")
    source.add_heading("正文验收", level=1)
    source.add_paragraph("正文内容。")
    source.save(tmp_path / "source.docx")
    output = tmp_path / "standard.docx"
    build_standard_docx(tmp_path / "source.docx", output, front_matter_dir=custom)

    assert_master_lists(output, figure=False, table=False)
    result = Document(output)
    paragraph = next(p for p in result.paragraphs if p.text == "独立编辑的封面")
    ds = Document(DEFAULT_DS_SECTIONS / "body.docx")
    assert paragraph.style.name == "DS主标题"
    assert paragraph.style.font.name == ds.styles["DS主标题"].font.name
    result_header = result.sections[0].header.paragraphs[0]
    assert result_header.text == "自定义封面页眉"
    (blip,) = result_header._p.xpath(".//a:blip")
    image = result_header.part.related_parts[blip.get(qn("r:embed"))]
    assert image.blob == Path(picture).read_bytes()
    assert result.sections[0].footer.paragraphs[0].text == "自定义封面页脚"
    assert all(
        "自定义封面页眉" not in paragraph.text
        for section in result.sections[1:]
        for paragraph in section.header.paragraphs
    )
    assert cover_path.read_bytes() == original


def simple_field(paragraph, instruction, cache=""):
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), instruction)
    paragraph._p.append(field)
    if cache:
        field.append(paragraph.add_run(cache)._r)


def test_file_finalization_removes_only_the_optional_page_and_its_break(tmp_path, picture):
    output = tmp_path / "final.docx"
    report = Document()
    report.add_paragraph("封面")
    report.add_page_break()
    report.add_paragraph("修订记录")
    report.add_page_break()
    report.add_paragraph("目 录")
    simple_field(report.add_paragraph(), r'TOC \o "1-6"')
    report.add_page_break()
    report.add_paragraph("图目录")
    simple_field(report.add_paragraph(), r'TOC \h \z \c "图"', "母版示例缓存")
    report.add_page_break()
    report.add_paragraph("表目录")
    simple_field(report.add_paragraph(), r'TOC \h \z \c "表"')
    report.add_page_break()
    report.add_heading("正文验收", level=1)
    simple_field(report.add_paragraph("表 "), "SEQ 表", "1")
    report.add_table(rows=1, cols=1).cell(0, 0).text = "通过"
    simple_field(report.add_paragraph("孤立图题注 "), "SEQ 图", "1")
    report.add_paragraph("独立正文。")
    report.add_picture(picture)
    report.add_page_break()
    report.add_paragraph("后一页的正文")
    report.save(output)

    assert prune_empty_caption_lists(str(output)) == Path(output)
    result = Document(output)
    text = [paragraph.text.strip() for paragraph in result.paragraphs]
    assert "图目录" not in text
    assert {"封面", "修订记录", "目 录", "表目录", "正文验收", "后一页的正文"} <= set(text)
    assert len(result.element.body.xpath('.//w:br[@w:type="page"]')) == 5
    assert len(result.inline_shapes) == 1
    after = output.read_bytes()
    prune_empty_caption_lists(output)
    assert output.read_bytes() == after


def test_list_sharing_a_page_with_user_content_is_preserved(tmp_path):
    path = tmp_path / "shared-page.docx"
    doc = Document()
    doc.add_paragraph("目录")
    simple_field(doc.add_paragraph(), r'TOC \o "1-6"')
    doc.add_page_break()
    doc.add_paragraph("图录")
    field_paragraph = doc.add_paragraph()
    simple_field(field_paragraph, r'TOC \c "图"')
    field_paragraph.add_run("用户正文与目录域放在同一段。")
    doc.save(path)

    before = path.read_bytes()
    prune_empty_caption_lists(path)
    assert path.read_bytes() == before
