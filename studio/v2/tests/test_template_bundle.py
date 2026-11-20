import io
import json
from urllib.parse import unquote
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from docxspec.report import render_report
from studio.v2.app import create_app
from studio.v2.compiler import compile_document
from studio.v2.models import DocumentModel


def upload_image(client, color):
    image = io.BytesIO()
    Image.new("RGB", (40, 24), color).save(image, "PNG")
    response = client.post("/api/v2/assets", files={"file": ("image.png", image.getvalue())})
    assert response.status_code == 200
    return response.json()["id"]


def test_template_bundle_export_round_trips_through_python_api(tmp_path):
    app = create_app(tmp_path / "studio")
    with TestClient(app) as client:
        asset_id = upload_image(client, "navy")
        unused_id = upload_image(client, "white")
        draft = {
            "header": "验收 · {{project.name}}",
            "nodes": [
                {"id": "h", "kind": "heading", "text": "测试报告"},
                {
                    "id": "enabled",
                    "kind": "condition",
                    "source": "report_enabled",
                    "equals": "true",
                    "children": [
                        {
                            "id": "repeat",
                            "kind": "repeat",
                            "source": "tests",
                            "children": [
                                {
                                    "id": "result",
                                    "kind": "table",
                                    "rows": [["测试项"], ["{{item.name}}"]],
                                },
                                {
                                    "id": "caption",
                                    "kind": "caption",
                                    "target": "result",
                                    "text": "{{item.name}}",
                                },
                            ],
                        },
                    ],
                },
                {"id": "picture", "kind": "image", "asset": asset_id},
            ],
        }
        payload = {"name": "设备/验收报告", "document": draft}
        response = client.post("/api/v2/template-bundles", json=payload)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert "设备_验收报告-模板包.zip" in unquote(response.headers["content-disposition"])
        bundle = tmp_path / "template.zip"
        bundle.write_bytes(response.content)
        with ZipFile(bundle) as package:
            assert set(package.namelist()) == {"template.json", f"assets/{asset_id}"}
            assert unused_id not in package.read("template.json").decode()
            manifest = json.loads(package.read("template.json"))
            assert "data" not in manifest
            assert manifest["name"] == payload["name"]
            assert (
                package.read(f"assets/{asset_id}")
                == client.get(f"/api/v2/assets/{asset_id}").content
            )

        data = {
            "project": {"name": "星河设备"},
            "report_enabled": True,
            "tests": [{"name": "液位校准"}, {"name": "过载保护"}],
        }
        studio_docx = tmp_path / "studio.docx"
        compile_document(
            DocumentModel.model_validate(draft), data, app.state.store.root / "assets", studio_docx
        )
        python_docx = render_report(bundle, data, tmp_path / "python.docx")
        with ZipFile(studio_docx) as studio, ZipFile(python_docx) as library:
            assert set(studio.namelist()) == set(library.namelist())
            for part in studio.namelist():
                assert library.read(part) == studio.read(part), part
            assert "液位校准" in library.read("word/document.xml").decode()

        # This route accepts exactly the portable snapshot and does not save a draft.
        assert (
            client.post("/api/v2/template-bundles", json={**payload, "data": data}).status_code
            == 422
        )
        assert app.state.store.templates() == []
