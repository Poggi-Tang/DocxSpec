"""Public report APIs, runnable against an installed wheel without a Studio checkout."""

import hashlib
import json
from zipfile import ZipFile

import pytest
from docx import Document
from lxml import etree
from PIL import Image

from docxspec.report import (
    BUNDLE_FORMAT,
    DocumentModel,
    Node,
    export_template_bundle,
    load_template_bundle,
    register_report_asset,
    render_report,
)


def _image(folder, name, color):
    path = folder / (name + ".png")
    Image.new("RGB", (20, 12), color).save(path)
    return path


def _report_with_repetition():
    return DocumentModel(
        header="项目 {{project.name}}",
        nodes=[
            Node(kind="heading", text="验收结论"),
            Node(
                kind="repeat",
                source="cases",
                children=[
                    Node(
                        id="results",
                        kind="table",
                        rows_source="item.rows",
                        header_rows=0,
                        rows=[["{{row.result}}"]],
                        style={"before": 4, "after": 5},
                    ),
                    Node(kind="caption", target="results", text="记录 {{item.name}}"),
                ],
            ),
            Node(
                kind="condition",
                source="showConclusion",
                equals="true",
                children=[Node(kind="paragraph", text="结论通过")],
            ),
        ],
    )


def test_portable_bundle_matches_direct_render(tmp_path):
    model = _report_with_repetition()
    data = {
        "project": {"name": "项目 A"},
        "cases": [
            {"name": "甲", "rows": [{"result": "通过"}]},
            {"name": "空", "rows": []},
            {"name": "乙", "rows": [{"result": "通过"}, {"result": "继续"}]},
        ],
        "showConclusion": True,
    }
    bundle_path = export_template_bundle(model, tmp_path / "report.zip", name="验收模板")
    bundle = load_template_bundle(bundle_path)
    assert bundle.name == "验收模板" and bundle.document == model and not bundle.asset_ids
    with ZipFile(bundle_path) as archive:
        manifest = json.loads(archive.read("template.json"))
        assert manifest["format"] == BUNDLE_FORMAT
        assert set(manifest) == {"format", "name", "document", "master_sha256", "asset_ids"}
        assert bundle.master_sha256 == manifest["master_sha256"]
        assert archive.namelist() == ["template.json"]
    direct = render_report(model.model_dump(), data, tmp_path / "direct.docx")
    portable = render_report(bundle, data, tmp_path / "portable.docx")
    with ZipFile(direct) as expected, ZipFile(portable) as actual:
        for member in (
            "docProps/core.xml",
            "word/document.xml",
            "word/styles.xml",
            "word/header1.xml",
            "word/footer1.xml",
        ):
            assert actual.read(member) == expected.read(member)
        core = etree.fromstring(actual.read("docProps/core.xml"))
        modifiers = core.xpath("./*[local-name()='lastModifiedBy']")
        assert len(modifiers) == 1
        assert modifiers[0].tag == (
            "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy"
        )
        assert modifiers[0].text == "DocxSpec"

    result = Document(portable)
    assert [p.text for p in result.paragraphs] == [
        "验收结论",
        "表 1-1 记录 甲",
        "表 1-2 记录 乙",
        "结论通过",
    ]
    assert [p.style.name for p in result.paragraphs] == [
        "DS一级标题",
        "DS题注",
        "DS题注",
        "DS正文",
    ]
    assert len(result.tables) == 2
    assert result.tables[1].cell(1, 0).text == "继续"
    fmt = result.tables[0].cell(0, 0).paragraphs[0].paragraph_format
    assert fmt.space_before.pt == 4 and fmt.space_after.pt == 5
    assert result.sections[0].header.paragraphs[0].text == "项目 项目 A"


def test_bundle_embeds_only_fixed_images_and_dynamic_assets_resolve(tmp_path):
    fixed = _image(tmp_path, "fixed", "blue")
    dynamic = _image(tmp_path, "dynamic", "green")
    unrelated = _image(tmp_path, "unrelated", "red")
    assets = tmp_path / "images"
    fixed_id = register_report_asset(fixed, assets)
    dynamic_id = register_report_asset(dynamic, assets)
    unrelated_id = register_report_asset(unrelated, assets)
    assert fixed_id == hashlib.sha256(fixed.read_bytes()).hexdigest()
    model = DocumentModel(
        nodes=[
            Node(kind="heading", text="报告"),
            Node(kind="image", asset=fixed_id),
            Node(kind="image", asset=unrelated_id, source="case.image"),
        ],
    )
    bundle = export_template_bundle(model, tmp_path / "bundle.zip", name="图片报告", assets=assets)
    with ZipFile(bundle) as archive:
        assert archive.namelist() == ["template.json", "assets/" + fixed_id]
        assert archive.read("assets/" + fixed_id) == fixed.read_bytes()

    # Fixed images are supplied by the bundle, not by the caller's asset folder.
    supplied = tmp_path / "runtime-assets"
    assert register_report_asset(dynamic, supplied) == dynamic_id
    output = render_report(
        bundle, {"case": {"image": dynamic_id}}, tmp_path / "report.docx", assets=supplied
    )
    result = Document(output)
    assert len(result.inline_shapes) == 2
    image_ids = [shape._inline.xpath(".//a:blip")[0].embed for shape in result.inline_shapes]
    assert [result.part.related_parts[image_id].blob for image_id in image_ids] == [
        fixed.read_bytes(),
        dynamic.read_bytes(),
    ]


def test_export_and_render_fail_without_replacing_existing_outputs(tmp_path):
    fixed = _image(tmp_path, "fixed", "blue")
    assets = tmp_path / "assets"
    digest = register_report_asset(fixed, assets)
    model = DocumentModel(nodes=[Node(kind="image", asset=digest)])
    bundle = export_template_bundle(model, tmp_path / "bundle.zip", name="图片", assets=assets)
    original_bundle = bundle.read_bytes()

    with pytest.raises(ValueError, match="图片资源不存在"):
        export_template_bundle(model, bundle, name="缺少图片")
    assert bundle.read_bytes() == original_bundle

    (assets / digest).write_bytes(b"corrupted")
    output = render_report(bundle, {}, tmp_path / "report.docx")
    original_document = output.read_bytes()
    with pytest.raises(ValueError, match="图片资源哈希不匹配"):
        render_report(model, {}, output, assets=assets)
    assert output.read_bytes() == original_document


def _copy_bundle(source, target, mutate):
    with ZipFile(source) as archive:
        contents = [(member.filename, archive.read(member)) for member in archive.infolist()]
    with ZipFile(target, "w") as archive:
        for name, raw in mutate(contents):
            archive.writestr(name, raw)
    return target


def test_bundle_rejects_unexpected_paths_and_duplicate_names(tmp_path):
    template = export_template_bundle(DocumentModel(), tmp_path / "template.zip", name="测试")
    traversal = _copy_bundle(
        template, tmp_path / "unexpected.zip", lambda items: [*items, ("../outside.txt", b"extra")]
    )
    with pytest.raises(ValueError, match="无效文件名"):
        load_template_bundle(traversal)
    assert not (tmp_path / "outside.txt").exists()

    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicate = _copy_bundle(template, tmp_path / "duplicate.zip", lambda items: items * 2)
    with pytest.raises(ValueError, match="重复"):
        load_template_bundle(duplicate)


def test_bundle_rejects_tampered_assets_and_a_different_master(tmp_path):
    fixed = _image(tmp_path, "fixed", "blue")
    assets = tmp_path / "assets"
    digest = register_report_asset(fixed, assets)
    template = export_template_bundle(
        DocumentModel(nodes=[Node(kind="image", asset=digest)]),
        tmp_path / "template.zip",
        name="图片",
        assets=assets,
    )
    wrong_asset = _copy_bundle(
        template,
        tmp_path / "edited.zip",
        lambda items: [
            (name, b"changed" if name.startswith("assets/") else raw) for name, raw in items
        ],
    )
    with pytest.raises(ValueError, match="图片资源哈希不匹配"):
        load_template_bundle(wrong_asset)

    def replace_master(items):
        for name, raw in items:
            if name == "template.json":
                manifest = json.loads(raw)
                manifest["master_sha256"] = "0" * 64
                raw = json.dumps(manifest).encode()
            yield name, raw

    other_master = _copy_bundle(template, tmp_path / "v2-master.zip", replace_master)
    bundle = load_template_bundle(other_master)
    assert bundle.master_sha256 == "0" * 64
    with pytest.raises(ValueError, match="DS 母版"):
        render_report(bundle, {}, tmp_path / "should-not-exist.docx")
    assert not (tmp_path / "should-not-exist.docx").exists()
