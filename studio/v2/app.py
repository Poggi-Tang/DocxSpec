from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from docxspec.report import export_template_bundle

from .compiler import compile_document
from .conversion import ai_status, convert, extract_docx
from .engines import capabilities, render
from .models import (
    DocumentModel,
    Node,
    TemplateInput,
    clone_node,
    initial_data,
    initial_document,
    presets,
)
from .storage import Conflict, Store

ROOT = Path(__file__).resolve().parent


class SetInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    engine: str = "word"


class RenderInput(BaseModel):
    document: DocumentModel
    data: dict = Field(default_factory=dict)
    engine: str


class TemplateBundleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    document: DocumentModel


class ComponentInput(BaseModel):
    set_id: str
    name: str = Field(min_length=1, max_length=100)
    node: Node


class ReviewMark(BaseModel):
    reviewed: bool


def download_label(name: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name[:200])
    # Leave room for the suffix within common filesystem byte limits.
    return cleaned.encode("utf-8")[:180].decode("utf-8", errors="ignore").strip(" .") or fallback


def create_app(data_dir: Path):
    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="DocxSpec Studio V2", lifespan=lifespan)
    store = Store(data_dir.resolve())
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ds-engine")
    app.state.store = store
    app.state.pool = pool

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        from urllib.parse import urlsplit

        host_name = urlsplit("http://" + host).hostname
        if host_name not in ("127.0.0.1", "localhost", "testserver") or request.headers.get(
            "origin"
        ) not in (None, "http://" + host):
            return JSONResponse({"detail": "只允许本机同源访问"}, status_code=403)
        try:
            size = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            return JSONResponse({"detail": "请求长度无效"}, status_code=400)
        if size > 20 * 1024 * 1024:
            return JSONResponse({"detail": "请求不能超过 20 MB"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def bad(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/v2/bootstrap")
    def bootstrap():
        from docx import Document

        from docxspec import DEFAULT_MASTER_TEMPLATE

        master = Document(DEFAULT_MASTER_TEMPLATE)
        styles = []
        for s in master.styles:
            if s.name.startswith("DS"):
                styles.append(
                    dict(
                        name=s.name, font=s.font.name, size=s.font.size.pt if s.font.size else None
                    )
                )
        return dict(
            sets=store.list_sets(),
            templates=store.templates(),
            presets=presets(),
            engines=capabilities(),
            styles=styles,
            ai=ai_status(),
            master_hash=hashlib.sha256(Path(DEFAULT_MASTER_TEMPLATE).read_bytes()).hexdigest(),
        )

    @app.post("/api/v2/sets")
    def new_set(body: SetInput):
        if body.engine not in ("word", "wps", "libreoffice"):
            raise ValueError("引擎无效")
        return store.create_set(body.name.strip(), body.engine)

    @app.put("/api/v2/sets/{key}")
    def update_set(key: str, body: SetInput):
        if body.engine not in ("word", "wps", "libreoffice"):
            raise ValueError("引擎无效")
        with store.db() as db:
            if not db.execute("SELECT 1 FROM sets WHERE id=?", (key,)).fetchone():
                raise KeyError("模板集不存在")
            db.execute("UPDATE sets SET name=?,engine=? WHERE id=?", (body.name, body.engine, key))
        return dict(id=key, **body.model_dump())

    @app.post("/api/v2/templates")
    def new_template(body: TemplateInput):
        return store.save_template(None, body)

    @app.post("/api/v2/template-bundles")
    def download_template_bundle(body: TemplateBundleInput):
        directory = TemporaryDirectory(prefix="docxspec-template-")
        try:
            output = export_template_bundle(
                body.document,
                Path(directory.name) / "template.zip",
                name=body.name,
                assets=store.root / "assets",
            )
        except Exception:
            directory.cleanup()
            raise
        return FileResponse(
            output,
            media_type="application/zip",
            filename=f"{download_label(body.name, '模板')}-模板包.zip",
            background=BackgroundTask(directory.cleanup),
        )

    @app.get("/api/v2/default")
    def default():
        return dict(document=initial_document(), data=initial_data())

    @app.get("/api/v2/templates/{key}")
    def get_template(key: str):
        return store.get_template(key)

    @app.put("/api/v2/templates/{key}")
    def update_template(key: str, body: TemplateInput):
        return store.save_template(key, body)

    @app.delete("/api/v2/templates/{key}")
    def archive(key: str):
        store.get_template(key)
        with store.db() as db:
            db.execute("UPDATE templates SET archived=1 WHERE id=?", (key,))
        return {"archived": True}

    @app.get("/api/v2/templates/{key}/versions")
    def versions(key: str):
        return store.revisions(key)

    @app.get("/api/v2/templates/{key}/versions/{version}")
    def revision(key: str, version: int):
        return store.get_revision(key, version)

    @app.get("/api/v2/templates/{key}/review")
    def conversion_review(key: str):
        return store.conversion_review(key)

    @app.put("/api/v2/templates/{key}/review/{index}")
    def mark_review(key: str, index: int, body: ReviewMark):
        return store.mark_conversion_review(key, index, body.reviewed)

    @app.get("/api/v2/components")
    def components(set_id: str):
        return store.components(set_id)

    @app.post("/api/v2/components")
    def save_component(body: ComponentInput):
        node = clone_node(body.node.model_dump())

        def clear_media(n):
            n["asset"] = ""
            for c in n["children"]:
                clear_media(c)

        clear_media(node)
        return store.create_component(body.set_id, body.name, node)

    @app.post("/api/v2/assets")
    async def upload(file: UploadFile):
        from PIL import Image, ImageOps

        raw = await file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError("图片不能超过 5 MB")
        try:
            with Image.open(io.BytesIO(raw)) as im:
                if im.width * im.height > 20000000:
                    raise ValueError("图片不能超过 2000 万像素")
                im = ImageOps.exif_transpose(im).convert("RGB")
                buffer = io.BytesIO()
                im.save(buffer, format="PNG")
                raw = buffer.getvalue()
        except Exception as exc:
            raise ValueError("图片无效或超过限制") from exc
        key = hashlib.sha256(raw).hexdigest()
        (store.root / "assets" / key).write_bytes(raw)
        return dict(id=key)

    @app.get("/api/v2/assets/{key}")
    def asset(key: str):
        if not re.fullmatch("[a-f0-9]{64}", key):
            raise HTTPException(404)
        p = store.root / "assets" / key
        if not p.is_file():
            raise HTTPException(404)
        return FileResponse(p, media_type="image/png")

    def render_task(key, body):
        try:
            if store.job(key)["status"] == "cancelled":
                return
            store.update_job(key, "compiling")
            folder = store.root / "renders" / key
            folder.mkdir(exist_ok=True)
            from docxspec import DEFAULT_MASTER_TEMPLATE

            master_hash = hashlib.sha256(Path(DEFAULT_MASTER_TEMPLATE).read_bytes()).hexdigest()
            anchors = compile_document(
                body.document, body.data, store.root / "assets", folder / "source.docx"
            )
            store.update_job(key, "rendering")
            if store.job(key)["status"] == "cancelled":
                return
            result = render(folder, body.engine, anchors)
            result["master_hash"] = master_hash
            result["input_hash"] = hashlib.sha256(
                json.dumps(body.model_dump(), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            (folder / "manifest.json").write_text(json.dumps(result, ensure_ascii=False))
            store.update_job(key, "ready", result)
        except Exception as exc:
            store.update_job(key, "failed", error=str(exc))

    @app.post("/api/v2/renders")
    def new_render(body: RenderInput):
        if not any(c["id"] == body.engine and c["available"] for c in capabilities()):
            raise ValueError("所选引擎不可用，没有自动切换")
        key = store.new_job(dict(kind="render", **body.model_dump()))
        pool.submit(render_task, key, body)
        return dict(id=key, status="queued")

    @app.get("/api/v2/jobs/{key}")
    def job(key: str):
        result = store.job(key)
        result.pop("payload", None)
        return result

    @app.delete("/api/v2/jobs/{key}")
    def cancel(key: str):
        store.cancel_job(key)
        return dict(status="cancelled")

    @app.get("/api/v2/artifacts/{key}/{filename}")
    def artifact(
        key: str, filename: str, download_name: str = "", download_version: int | None = None
    ):
        if (
            filename not in ("report.docx", "report.pdf", "manifest.json")
            or store.job(key)["status"] != "ready"
        ):
            raise HTTPException(404)
        suggested_name = filename
        if filename == "report.docx" and download_name and download_version is not None:
            suggested_name = f"{download_label(download_name, '报告')}-v{download_version}.docx"
        return FileResponse(store.root / "renders" / key / filename, filename=suggested_name)

    def ai_task(key, blocks, set_id, name):
        try:
            if store.job(key)["status"] == "cancelled":
                return
            store.update_job(key, "analyzing")
            result = convert(blocks)
            store.complete_conversion_job(
                key,
                TemplateInput(
                    name=name, set_id=set_id, document=result["document"], data=result["data"]
                ),
                result,
            )
        except Exception as exc:
            store.update_job(key, "failed", error=str(exc))

    @app.post("/api/v2/conversions")
    async def convert_report(set_id: str, name: str, file: UploadFile):
        if not ai_status()["configured"]:
            raise ValueError("AI 未配置，请先设置模型服务；不会用规则转换冒充 AI")
        if not any(s["id"] == set_id for s in store.list_sets()):
            raise KeyError("模板集不存在")
        if not name.strip() or len(name) > 100:
            raise ValueError("模板名称无效")
        raw = await file.read(10 * 1024 * 1024 + 1)
        blocks = extract_docx(raw)
        key = store.new_job(dict(kind="conversion", set_id=set_id, name=name))
        pool.submit(ai_task, key, blocks, set_id, name)
        return dict(id=key, status="queued")

    web = ROOT / "web/dist"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


def main():
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=4177)
    p.add_argument("--data-dir", type=Path, default=ROOT / ".data")
    args = p.parse_args()
    uvicorn.run(create_app(args.data_dir), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
