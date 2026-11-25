import io
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from docx import Document
from fastapi.testclient import TestClient

from studio.v2.app import create_app
from studio.v2.compiler import compile_document
from studio.v2.conversion import convert, extract_docx
from studio.v2.models import (
    DocumentModel,
    Node,
    TemplateInput,
    clone_node,
    initial_data,
    initial_document,
)
from studio.v2.storage import Conflict, Store


def test_storage_conflict_and_revision(tmp_path):
    store = Store(tmp_path)
    s = store.create_set("测试模板集", "word")
    body = TemplateInput(
        name="报告", set_id=s["id"], document=DocumentModel.model_validate(initial_document())
    )
    first = store.save_template(None, body)
    body.version = 1
    body.name = "新版"
    second = store.save_template(first["id"], body)
    assert second["version"] == 2
    assert store.save_template(first["id"], body) == second
    body.document.header = "旧版本草稿"
    with pytest.raises(Conflict):
        store.save_template(first["id"], body)
    assert store.get_template(first["id"]) == second
    assert store.get_revision(first["id"], 1)["name"] == "报告"
    assert len(store.revisions(first["id"])) == 2


def test_conversion_completion_respects_cancellation_and_persists_review(tmp_path):
    store = Store(tmp_path)
    owner = store.create_set("测试模板集", "word")
    body = TemplateInput(name="报告", set_id=owner["id"], document=DocumentModel())
    result = {"review": [{"decision": "保留"}], "source_blocks": [{"source_id": "p0"}]}
    cancelled = store.new_job({"kind": "conversion"})
    store.update_job(cancelled, "analyzing")
    store.cancel_job(cancelled)
    store.complete_conversion_job(cancelled, body, result)
    assert store.templates() == []
    assert store.job(cancelled)["status"] == "cancelled"

    completed = store.new_job({"kind": "conversion"})
    store.update_job(completed, "analyzing")
    store.complete_conversion_job(completed, body, result)
    store.cancel_job(completed)
    reopened = Store(tmp_path)
    job = reopened.job(completed)
    assert job["status"] == "ready"
    template = reopened.get_template(job["result"]["template_id"])
    assert template["version"] == 1
    assert reopened.conversion_review(template["id"]) == {
        **result,
        "template_id": template["id"],
        "reviewed_indices": [],
    }


def test_conversion_review_marks_are_validated_and_persisted(tmp_path):
    app = create_app(tmp_path)
    store = app.state.store
    owner = store.create_set("审核模板集", "word")
    body = TemplateInput(name="报告", set_id=owner["id"], document=DocumentModel())
    job = store.new_job({"kind": "conversion"})
    store.update_job(job, "analyzing")
    store.complete_conversion_job(job, body, {"review": [{"decision": "保留"}]})
    template_id = store.job(job)["result"]["template_id"]
    path = f"/api/v2/templates/{template_id}/review"
    with TestClient(app) as client:
        assert client.put(path + "/1", json={"reviewed": True}).status_code == 404
        for _ in range(2):
            response = client.put(path + "/0", json={"reviewed": True})
            assert response.json()["reviewed_indices"] == [0]
        assert Store(tmp_path).conversion_review(template_id)["reviewed_indices"] == [0]
        assert client.put(path + "/0", json={"reviewed": False}).json()["reviewed_indices"] == []
        assert client.get(path).json()["reviewed_indices"] == []


def test_conversion_does_not_publish_a_template_if_ready_write_fails(tmp_path):
    store = Store(tmp_path)
    owner = store.create_set("测试模板集", "word")
    body = TemplateInput(name="报告", set_id=owner["id"], document=DocumentModel())
    job = store.new_job({"kind": "conversion"})
    store.update_job(job, "analyzing")
    with store.db() as db:
        db.execute("""
            CREATE TRIGGER reject_conversion_result
            BEFORE UPDATE ON jobs
            WHEN NEW.status='ready'
            BEGIN SELECT RAISE(ABORT, 'test ready write failed'); END
        """)
    with pytest.raises(sqlite3.IntegrityError, match="test ready write failed"):
        store.complete_conversion_job(job, body, {"review": []})
    assert store.templates() == []
    assert store.job(job)["status"] == "analyzing"
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0


def test_model_duplicate_and_clone_refs():
    table = Node(kind="table", id="table")
    caption = Node(kind="caption", target="table")
    group = Node(kind="group", children=[table, caption]).model_dump()
    result = clone_node(group)
    assert result["children"][1]["target"] == result["children"][0]["id"] != "table"
    with pytest.raises(ValueError):
        DocumentModel(nodes=[table, table])


def test_compile_repeat_caption_and_ds(tmp_path):
    table = Node(
        kind="table", id="t", rows=[["项目", "结果"], ["{{item.name}}", "{{item.result}}"]]
    )
    doc = DocumentModel(
        nodes=[
            Node(kind="heading", text="验收"),
            Node(
                kind="repeat",
                source="testCases",
                children=[table, Node(kind="caption", target="t", text="用例")],
            ),
        ]
    )
    data = {"testCases": [{"name": "A", "result": "通过"}, {"name": "B", "result": "失败"}]}
    out = tmp_path / "source.docx"
    anchors = compile_document(doc, data, tmp_path, out)
    d = Document(out)
    assert len(d.tables) == 2
    assert d.paragraphs[0].paragraph_format.keep_with_next is True
    assert d.tables[0].rows[-1].cells[0].paragraphs[0].paragraph_format.keep_with_next is True
    assert d.tables[1].cell(1, 0).text == "B"
    assert [p.text for p in d.paragraphs if p.style.name == "DS题注"] == [
        "表 1-1 用例",
        "表 1-2 用例",
    ]
    assert "PAGE" in d.sections[0].footer._element.xml
    assert all(p.style.name.startswith("DS") for p in d.paragraphs)
    assert len(anchors) == 5


def test_missing_data_and_caption_fail(tmp_path):
    with pytest.raises(ValueError, match="缺少数据"):
        compile_document(
            DocumentModel.model_validate(initial_document()), {}, tmp_path, tmp_path / "bad.docx"
        )
    with pytest.raises(ValueError, match="题注"):
        compile_document(
            DocumentModel(nodes=[Node(kind="caption", text="孤立题注")]),
            {},
            tmp_path,
            tmp_path / "bad.docx",
        )


@pytest.mark.parametrize("rows", [[], [{"result": "通过"}]])
def test_caption_cannot_bind_to_a_sibling_repeat_even_at_the_same_index(tmp_path, rows):
    doc = DocumentModel(
        nodes=[
            Node(
                kind="repeat",
                source="arrays",
                children=[
                    Node(
                        kind="table",
                        id="target",
                        rows_source="rows",
                        header_rows=0,
                        rows=[["{{row.result}}"]],
                    )
                ],
            ),
            Node(
                kind="repeat",
                source="arrays",
                children=[Node(kind="caption", target="target", text="错绑的表题注")],
            ),
        ]
    )
    with pytest.raises(ValueError, match="同一重复范围"):
        compile_document(doc, {"arrays": [{}], "rows": rows}, tmp_path, tmp_path / "bad.docx")


def test_caption_for_empty_table_occurrence_is_omitted_without_consuming_number(tmp_path):
    doc = DocumentModel(
        nodes=[
            Node(kind="heading", text="报告"),
            Node(
                kind="repeat",
                source="runs",
                children=[
                    Node(
                        kind="table",
                        id="result-table",
                        rows_source="item.rows",
                        header_rows=0,
                        rows=[["{{row.name}}"]],
                    ),
                    Node(kind="caption", target="result-table", text="{{item.title}}"),
                ],
            ),
        ]
    )
    output = tmp_path / "report.docx"
    compile_document(
        doc,
        {"runs": [{"rows": []}, {"title": "通过项", "rows": [{"name": "正常"}]}]},
        tmp_path,
        output,
    )
    rendered = Document(output)
    assert [p.text for p in rendered.paragraphs if p.style.name == "DS题注"] == ["表 1-1 通过项"]
    assert len(rendered.tables) == 1
    assert rendered.tables[0].cell(0, 0).text == "正常"


def test_table_applies_paragraph_spacing_to_header_and_body(tmp_path):
    node = Node(
        kind="table",
        rows=[["结果"], ["通过"]],
        style={"before": 36, "after": 0},
    )
    output = tmp_path / "spacing.docx"
    compile_document(DocumentModel(nodes=[node]), {}, tmp_path, output)
    for row in Document(output).tables[0].rows:
        paragraph = row.cells[0].paragraphs[0]
        assert paragraph.paragraph_format.space_before.pt == 36
        assert paragraph.paragraph_format.space_after.pt == 0


def test_api_and_host_guard(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        assert c.get("/api/v2/bootstrap", headers={"origin": "http://evil.test"}).status_code == 403
        s = c.post("/api/v2/sets", json={"name": "模板集"}).json()
        body = dict(name="报告", set_id=s["id"], document=initial_document(), data=initial_data())
        t = c.post("/api/v2/templates", json=body).json()
        assert t["version"] == 1
        assert c.put("/api/v2/templates/" + t["id"], json={**body, "version": 0}).status_code == 409
        r = c.post(
            "/api/v2/renders",
            json={"document": body["document"], "data": body["data"], "engine": "wps"},
        )
        assert r.status_code == 400 and "没有自动切换" in r.text
        assert c.get("/api/v2/assets/not-a-hash").status_code == 404
    app.state.pool.shutdown()


def test_ai_adapter_preserves_unaccounted_and_resets_styles(tmp_path, monkeypatch):
    document = DocumentModel(
        nodes=[Node(id="n", kind="heading", text="固定内容", style={"size": 40, "font": "source"})]
    ).model_dump()
    document["page"]["width"] = 30
    response = {
        "document": document,
        "data": {},
        "review": [
            {
                "source_ids": ["p0"],
                "node_ids": ["n"],
                "decision": "固定文字",
                "reason": "原文",
                "needs_confirmation": True,
            }
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert "source_blocks" in body["messages"][1]["content"]
            result = json.dumps(
                {"choices": [{"message": {"content": json.dumps(response)}}]}
            ).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("STUDIO_AI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("STUDIO_AI_MODEL", "test-model")
    try:
        result = convert(
            [
                {"source_id": "p0", "kind": "paragraph", "text": "固定内容"},
                {"source_id": "p1", "kind": "paragraph", "text": "不能丢失"},
            ]
        )
        assert result["document"]["nodes"][0]["style"]["font"] is None
        assert result["document"]["page"]["width"] == 21
        assert result["document"]["nodes"][-1]["text"] == "不能丢失"
        assert result["review"][-1]["needs_confirmation"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_extract_source_styles_never_sent():
    d = Document()
    p = d.add_paragraph("源文字")
    p.runs[0].font.name = "Source Font"
    d.add_table(rows=1, cols=1).cell(0, 0).text = "表格文字"
    buf = io.BytesIO()
    d.save(buf)
    blocks = extract_docx(buf.getvalue())
    assert blocks[0]["text"] == "源文字" and blocks[1]["rows"] == [["表格文字"]]
    assert "Source Font" not in json.dumps(blocks)


def test_real_office_multipage(tmp_path):
    """Opt-in integration test: launches the actual installed Office engine."""
    import hashlib
    import os

    import pymupdf
    from PIL import Image

    from studio.v2.engines import render

    if os.environ.get("STUDIO_TEST_OFFICE") != "1":
        pytest.skip("Set STUDIO_TEST_OFFICE=1 to run actual LibreOffice rendering")
    picture = tmp_path / "picture.png"
    Image.new("RGB", (800, 400), "#c4d3e5").save(picture)
    digest = hashlib.sha256(picture.read_bytes()).hexdigest()
    (tmp_path / digest).write_bytes(picture.read_bytes())
    nodes = [
        Node(kind="heading", text="多页排版验收"),
        Node(
            kind="repeat",
            source="cases",
            children=[
                Node(kind="heading", level=2, text="{{item.title}}"),
                Node(
                    kind="table",
                    id="table",
                    rows=[["项目", "内容"], ["步骤", "{{item.steps}}"], ["结论", "通过"]],
                ),
                Node(kind="caption", target="table", text="验证结果"),
            ],
        ),
        Node(kind="image", id="image", asset=digest),
        Node(kind="caption", caption_type="figure", target="image", text="参考截图"),
    ]
    data = {
        "cases": [
            {"title": f"用例 {i + 1}", "steps": "按要求执行并检查实际行为。" * 12}
            for i in range(12)
        ]
    }
    anchors = compile_document(DocumentModel(nodes=nodes), data, tmp_path, tmp_path / "source.docx")
    result = render(tmp_path, "libreoffice", anchors)
    with pymupdf.open(tmp_path / "report.pdf") as doc:
        assert len(doc) >= 3
        texts = ["".join(page.get_text().split()) for page in doc]
        for i, text in enumerate(texts):
            assert f"第{i + 1}页/共{len(doc)}页" in text
            assert not any(text.endswith(f"用例{k}") for k in range(1, 13))
        assert "表1-12验证结果" in "".join(texts)
        assert "图1-1参考截图" in texts[-1]
        assert len(doc[-1].get_images()) > 0
    assert result["pages"] >= 3 and result["mapping"]
    for name, digest in result["hashes"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest


def test_real_libreoffice_updates_saved_directory_and_footer(tmp_path):
    import os
    from zipfile import ZipFile

    import pymupdf
    from docx import Document
    from lxml import etree

    from docxspec._field_xml import iter_field_results, story_parts
    from docxspec._libreoffice_fields import uno_command
    from studio.make_field_probe import field
    from studio.v2.engines import render

    if os.environ.get("STUDIO_TEST_OFFICE") != "1":
        pytest.skip("Set STUDIO_TEST_OFFICE=1 to run actual LibreOffice rendering")
    source = tmp_path / "source.docx"
    report = tmp_path / "report.docx"
    if uno_command(source, report) is None:
        pytest.skip("LibreOffice UNO Python bindings are unavailable")
    doc = Document()
    field(doc.add_paragraph(), r'TOC \o "1-2"', "STALE TOC")
    doc.add_heading("First section", level=1)
    doc.add_page_break()
    doc.add_heading("Second section", level=1)
    footer = doc.sections[0].footer.paragraphs[0]
    footer.add_run("Page ")
    field(footer, "PAGE", "999")
    footer.add_run(" of ")
    field(footer, "NUMPAGES", "999")
    doc.save(source)

    result = render(tmp_path, "libreoffice", [])
    assert result["field_state"] == "refreshed"
    assert result["field_issues"] == []
    with ZipFile(report) as package:
        values = [
            (code.strip(), text)
            for name, _ in story_parts(package)
            for _, code, text in iter_field_results(etree.fromstring(package.read(name)))
        ]
    assert any(code.startswith("TOC") and "Second section" in value for code, value in values)
    assert ("NUMPAGES", "2") in values
    assert all("999" not in value and "STALE TOC" not in value for _, value in values)
    with pymupdf.open(tmp_path / "report.pdf") as pdf:
        assert "Page 1 of 2" in pdf[0].get_text()
        assert "Page 2 of 2" in pdf[1].get_text()


def test_invalid_or_oversized_source_is_not_silently_truncated():
    with pytest.raises(ValueError, match="有效的 DOCX"):
        extract_docx(b"not a docx")
    d = Document()
    d.add_paragraph("x" * 20001)
    buffer = io.BytesIO()
    d.save(buffer)
    with pytest.raises(ValueError, match="拆分"):
        extract_docx(buffer.getvalue())


def test_download_filename_does_not_change_the_bound_artifact(tmp_path):
    from urllib.parse import unquote

    app = create_app(tmp_path)
    store = app.state.store
    job = store.new_job({"kind": "render"})
    store.update_job(job, "ready", {})
    folder = tmp_path / "renders" / job
    folder.mkdir()
    (folder / "report.docx").write_bytes(b"render bytes")
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/artifacts/{job}/report.docx",
            params={"download_name": "../版本:二?内容", "download_version": 7},
        )
        assert response.status_code == 200
        assert response.content == b"render bytes"
        assert unquote(response.headers["content-disposition"]).endswith("_版本_二_内容-v7.docx")
