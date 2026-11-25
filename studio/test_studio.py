import base64
import io
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree
from docxspec import DEFAULT_DS_SECTIONS
from model import validate
from PIL import Image
from renderer import render_docx
from server import Conflict, Store


def fixture():
    return dict(
        schema="docxspec-studio-v1",
        section=2,
        sections=["封面", "概况", "明细", "结论"],
        intro="验证数据 & XML < >",
        source="测试用例",
        repeat="每条记录",
        empty="隐藏区块",
        selected=0,
        format={
            "0": dict(
                size=20,
                line="2",
                color="#abcdef",
                style="DS正文",
                bold=True,
                italic=True,
                center=True,
            )
        },
        texts={"0": "持久化封面文字"},
        cases=[
            dict(
                id="TC-1",
                name="中文正常用例",
                steps=["步骤一", "步骤二"],
                expected="正常 <正常> & {{literal}}",
                actual="实际结果",
                result="通过",
            ),
            dict(
                id="TC-2",
                name="中文失败用例",
                steps=["步骤"],
                expected="拒绝",
                actual="错误",
                result="失败",
            ),
        ],
    )


class StudioTests(unittest.TestCase):
    def test_render_styles_image_and_xml(self):
        data = fixture()
        im = Image.new("RGB", (80, 40), "blue")
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        data["cases"][0]["image"] = (
            "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        )
        raw = render_docx(data)
        doc = Document(io.BytesIO(raw))
        self.assertEqual(len(doc.tables), 4)
        self.assertEqual(doc.tables[2].cell(1, 1).text, "正常 <正常> & {{literal}}")
        self.assertIn("1. 步骤一\n2. 步骤二", doc.tables[2].cell(0, 1).text)
        self.assertEqual(len(doc.inline_shapes), 1)
        self.assertEqual(doc.tables[2].cell(1, 1).paragraphs[0].runs[0].font.size.pt, 15)
        self.assertIn("abcdef", doc.tables[2]._tbl.xml)
        self.assertIn("持久化封面文字", "\n".join(p.text for p in doc.paragraphs))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn(b"updateFields", z.read("word/settings.xml"))
            self.assertNotIn(b"KL", z.read("word/styles.xml"))
            xml = z.read("word/document.xml").decode("utf-8")
            self.assertNotIn("{{p report}}", xml)
            self.assertIn('TOC \\h \\z \\c "图"', xml)
            self.assertIn('TOC \\h \\z \\c "表"', xml)

    def test_word_refresh_is_explicit_and_failures_stop_export(self):
        from unittest.mock import patch

        with patch("renderer.refresh_docx_fields") as refresh:
            render_docx(fixture())
            self.assertEqual(refresh.call_args.kwargs["engine"], "mark")
            render_docx(fixture(), refresh_fields=True)
            self.assertEqual(refresh.call_args.kwargs["engine"], "word")
            self.assertTrue(refresh.call_args.kwargs["strict"])
        with patch("renderer.refresh_docx_fields", side_effect=RuntimeError("Word failed")):
            with self.assertRaisesRegex(RuntimeError, "Word failed"):
                render_docx(fixture(), refresh_fields=True)

    def test_master_template_styles_and_furniture_are_preserved(self):
        data = fixture()
        data["format"] = {}
        raw = render_docx(data)
        doc = Document(io.BytesIO(raw))
        source = Document(DEFAULT_DS_SECTIONS / "body.docx")
        self.assertEqual(len(doc.sections), 5)
        self.assertEqual(doc.sections[-1].left_margin, source.sections[-1].left_margin)
        for style in source.styles:
            if style.name.startswith(("DS", "toc ")):
                expected = deepcopy(style.element)
                actual = deepcopy(doc.styles[style.name].element)
                priority = actual.find(qn("w:uiPriority"))
                if priority is not None:
                    # The value is preserved while export corrects the source element order.
                    quick_format = actual.find(qn("w:qFormat"))
                    if quick_format is not None:
                        self.assertLess(actual.index(priority), actual.index(quick_format))
                    actual.remove(priority)
                    actual.insert(expected.index(expected.find(qn("w:uiPriority"))), priority)
                self.assertEqual(
                    etree.tostring(expected, method="c14n"),
                    etree.tostring(actual, method="c14n"),
                    style.name,
                )
        paragraph = doc.tables[2].cell(1, 1).paragraphs[0]
        self.assertEqual(paragraph.style.name, "DS表格文字")
        self.assertIsNone(paragraph.runs[0].font.name)
        self.assertIsNone(paragraph.runs[0].font.size)
        self.assertEqual(doc.tables[2].cell(0, 0).paragraphs[0].style.name, "DS表格表头")
        self.assertNotIn("3　明细", "\n".join(p.text for p in doc.paragraphs))
        for name, section in zip(("cover", "revision", "contents", "tables", "body"), doc.sections):
            original = Document(DEFAULT_DS_SECTIONS / f"{name}.docx").sections[0]
            for story in ("header", "first_page_header", "footer", "first_page_footer"):
                expected = getattr(original, story).part.element
                actual = getattr(section, story).part.element
                for xpath in (".//w:t/text()", ".//w:instrText/text()"):
                    self.assertEqual(
                        expected.xpath(xpath),
                        actual.xpath(xpath),
                        name,
                    )
        with zipfile.ZipFile(io.BytesIO(raw)) as result:
            xml = result.read("word/document.xml").decode("utf-8")
            self.assertIn('TOC \\o', xml)
            self.assertNotIn('TOC \\h \\z \\c "图"', xml)
            self.assertIn('TOC \\h \\z \\c "表"', xml)
            self.assertIn("STYLEREF DS一级标题", xml)
            self.assertIn("SEQ 表", xml)
            self.assertNotIn("DS六级标题</w:t>", xml)

    def test_filters_and_empty(self):
        d = fixture()
        d["source"] = "失败用例"
        doc = Document(io.BytesIO(render_docx(d)))
        self.assertEqual(len(doc.tables), 3)
        self.assertIn("TC-2", "\n".join(p.text for p in doc.paragraphs))
        d["source"] = "测试用例"
        d["repeat"] = "仅首条记录"
        self.assertEqual(len(Document(io.BytesIO(render_docx(d))).tables), 3)
        d["cases"] = []
        d["empty"] = "显示待补充"
        doc = Document(io.BytesIO(render_docx(d)))
        self.assertEqual(len(doc.tables), 2)
        self.assertIn("测试数据待补充", "\n".join(p.text for p in doc.paragraphs))
        d["empty"] = "隐藏区块"
        self.assertNotIn(
            "测试数据待补充",
            "\n".join(p.text for p in Document(io.BytesIO(render_docx(d))).paragraphs),
        )

    def test_persistence_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite3"
            store = Store(path)
            r = store.save(dict(name="测试模板", document=fixture()))
            self.assertEqual(Store(path).get(r["id"])["document"], validate(fixture()))
            edit = dict(id=r["id"], version=1, name="修改", document=fixture())
            self.assertEqual(store.save(edit)["version"], 2)
            with self.assertRaises(Conflict):
                store.save(edit)
            self.assertEqual(store.get(r["id"])["version"], 2)

    def test_partial_style_change_keeps_other_properties_inherited(self):
        data = fixture()
        data["format"] = {"0": {"italic": True}}
        self.assertEqual(validate(data)["format"], {"0": {"italic": True}})
        doc = Document(io.BytesIO(render_docx(data)))
        paragraph = doc.tables[2].cell(1, 1).paragraphs[0]
        self.assertEqual(paragraph.style.name, "DS表格文字")
        self.assertTrue(paragraph.runs[0].italic)
        self.assertIsNone(paragraph.runs[0].font.size)
        self.assertIsNone(paragraph.paragraph_format.line_spacing)

    def test_master_chapters_are_read_from_docx_and_exported_at_original_levels(self):
        from master import HEADING_STYLES, master_document

        defaults = master_document()
        data = validate(defaults["document"])
        master = Document(DEFAULT_DS_SECTIONS / "body.docx")
        headings = [
            (p.text.strip(), p.style.name) for p in master.paragraphs
            if p.style.name in HEADING_STYLES
            and p.text.strip() == p.style.name
        ]
        self.assertEqual(data["sections"][:5], ["封面", "修改记录", "目录", "图目录", "表目录"])
        self.assertEqual(data["sections"][5:], [text for text, _ in headings])
        self.assertEqual([item["level"] for item in data["section_meta"][5:]], [1, 2, 3, 4, 5, 6] * 2)
        self.assertEqual(data["section_meta"][data["section"]]["kind"], "cases")
        data["sections"][5] = "母版第一章"
        output = Document(io.BytesIO(render_docx(data)))
        exported = [(p.text, p.style.name) for p in output.paragraphs if p.style.name in HEADING_STYLES]
        exported = exported[exported.index(("母版第一章", "DS一级标题")):]
        expected = [("母版第一章", headings[0][1]), *headings[1:]]
        self.assertEqual(exported, expected)
        self.assertEqual(len(output.sections), 5)
        self.assertEqual(len(output.tables), 4)
        self.assertNotIn("修改记录", [p.text for p in output.paragraphs if p.style.name == "DS一级标题"])
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "library.sqlite3")
            record = store.save(dict(name="母版结构", document=data))
            self.assertEqual(store.get(record["id"])["document"]["section_meta"], data["section_meta"])
        data["section_meta"][6]["level"] = 7
        with self.assertRaisesRegex(ValueError, "标题级别"):
            validate(data)

    def test_invalid_imports(self):
        for key, value in [
            ("schema", "unknown"),
            ("cases", [{}]),
            ("format", {"0": {"color": "red;bad"}}),
            ("sections", []),
            ("selected", -1),
        ]:
            with self.subTest(key=key):
                d = fixture()
                d[key] = value
                with self.assertRaises(ValueError):
                    validate(d)
        d = fixture()
        d["cases"][0]["image"] = "data:image/png;base64,YmFk"
        with self.assertRaises(ValueError):
            validate(d)
        d = fixture()
        d["schema"] = "docxspec-studio-prototype-v1"
        self.assertEqual(validate(d)["schema"], "docxspec-studio-v1")


if __name__ == "__main__":
    unittest.main()
