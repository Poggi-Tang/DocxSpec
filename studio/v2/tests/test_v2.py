import io
import json
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
    with pytest.raises(Conflict):
        store.save_template(first["id"], body)
    assert store.get_revision(first["id"], 1)["name"] == "报告"
    assert len(store.revisions(first["id"])) == 2


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


def test_invalid_or_oversized_source_is_not_silently_truncated():
    with pytest.raises(ValueError, match="有效的 DOCX"):
        extract_docx(b"not a docx")
    d = Document()
    d.add_paragraph("x" * 20001)
    buffer = io.BytesIO()
    d.save(buffer)
    with pytest.raises(ValueError, match="拆分"):
        extract_docx(buffer.getvalue())
