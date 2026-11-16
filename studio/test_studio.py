import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
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
        self.assertEqual(len(doc.tables), 2)
        self.assertEqual(doc.tables[0].cell(1, 1).text, "正常 <正常> & {{literal}}")
        self.assertIn("1. 步骤一\n2. 步骤二", doc.tables[0].cell(0, 1).text)
        self.assertEqual(len(doc.inline_shapes), 1)
        self.assertEqual(doc.tables[0].cell(1, 1).paragraphs[0].runs[0].font.size.pt, 15)
        self.assertIn("abcdef", doc.tables[0]._tbl.xml)
        self.assertIn("持久化封面文字", "\n".join(p.text for p in doc.paragraphs))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn(b"updateFields", z.read("word/settings.xml"))
            self.assertNotIn(b"KL", z.read("word/styles.xml"))
            self.assertNotIn(b"{{p report}}", z.read("word/document.xml"))

    def test_filters_and_empty(self):
        d = fixture()
        d["source"] = "失败用例"
        doc = Document(io.BytesIO(render_docx(d)))
        self.assertEqual(len(doc.tables), 1)
        self.assertIn("TC-2", "\n".join(p.text for p in doc.paragraphs))
        d["source"] = "测试用例"
        d["repeat"] = "仅首条记录"
        self.assertEqual(len(Document(io.BytesIO(render_docx(d))).tables), 1)
        d["cases"] = []
        d["empty"] = "显示待补充"
        doc = Document(io.BytesIO(render_docx(d)))
        self.assertEqual(len(doc.tables), 0)
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
