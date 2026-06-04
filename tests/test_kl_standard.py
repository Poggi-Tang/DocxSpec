"""KL 标准能力测试。"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from docxspec import (
    DEFAULT_MASTER_TEMPLATE,
    build_standard_docx,
    check_word_standard,
    classify_docx_body,
    classify_heading,
    clean_heading_number,
)


def test_clean_heading_number_and_classify_heading() -> None:
    cleaned, kind = clean_heading_number("1.2 接口设计")

    assert cleaned == "接口设计"
    assert kind == "heading_2"
    assert classify_heading("第一章 需求背景")[0] == "heading_1"
    assert classify_heading("① 这是正文条目")[0] == "body"


def test_classify_docx_body_reports_headings_tables_and_captions(tmp_path: Path) -> None:
    docx = tmp_path / "body.docx"
    doc = Document()
    doc.add_paragraph("一、需求背景")
    doc.add_paragraph("这是正文内容。")
    doc.add_paragraph("表 1-1 数据表")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "字段"
    table.cell(0, 1).text = "值"
    table.cell(1, 0).text = "名称"
    table.cell(1, 1).text = "积分元件"
    doc.save(docx)

    report = classify_docx_body(docx)

    assert report["summary"]["heading_1"] == 1
    assert report["summary"]["body"] == 1
    assert report["summary"]["table_caption"] == 1
    assert report["summary"]["table"] == 1
    assert report["tables"][0]["caption"]["position"] == "above"


def test_check_word_standard_uses_template_styles() -> None:
    template = Path(__file__).parent / "templates" / "template.docx"

    report = check_word_standard(template)

    assert report["required_styles_ok"] is True
    assert report["missing_styles"] == []


def test_default_master_template_is_packaged() -> None:
    assert DEFAULT_MASTER_TEMPLATE.exists()
    report = check_word_standard(DEFAULT_MASTER_TEMPLATE)
    assert report["required_styles_ok"] is True


def test_build_standard_docx_from_body_document(tmp_path: Path) -> None:
    template = Path(__file__).parent / "templates" / "template.docx"
    body = tmp_path / "body.docx"
    output = tmp_path / "standard.docx"

    doc = Document()
    doc.add_paragraph("积分元件测试大纲")
    doc.add_paragraph("1 需求背景")
    doc.add_paragraph("这是正文内容。")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "字段"
    table.cell(0, 1).text = "值"
    table.cell(1, 0).text = "名称"
    table.cell(1, 1).text = "积分元件"
    doc.save(body)

    report = build_standard_docx(body, output, template)

    assert output.exists()
    assert report["source_title"] == "积分元件测试大纲"
    assert report["tables_styled"] >= 1
    standard_report = check_word_standard(output)
    assert standard_report["required_styles_ok"] is True


def test_build_standard_docx_uses_packaged_template_by_default(tmp_path: Path) -> None:
    body = tmp_path / "body.docx"
    output = tmp_path / "standard_default.docx"

    doc = Document()
    doc.add_paragraph("积分元件测试大纲")
    doc.add_paragraph("1 需求背景")
    doc.add_paragraph("这是正文内容。")
    doc.save(body)

    report = build_standard_docx(body, output)

    assert output.exists()
    assert report["template"] == str(DEFAULT_MASTER_TEMPLATE)
    assert check_word_standard(output)["required_styles_ok"] is True
