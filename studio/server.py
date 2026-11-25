"""Local-only Studio service. Run: python studio/server.py --port 4175."""

import argparse
import json
import mimetypes
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))
from master import master_document  # noqa: E402
from model import validate  # noqa: E402
from renderer import render_docx  # noqa: E402

MAX_BODY = 25 * 1024 * 1024


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS templates (id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, version INTEGER NOT NULL, updated TEXT NOT NULL, "
                "document TEXT NOT NULL)"
            )

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def list(self):
        with closing(self.connect()) as db, db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,name,version,updated FROM templates ORDER BY updated DESC"
                )
            ]

    def get(self, key):
        with closing(self.connect()) as db, db:
            row = db.execute("SELECT * FROM templates WHERE id=?", (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            value = dict(row)
            value["document"] = json.loads(value["document"])
            return value

    def save(self, data):
        doc = validate(data.get("document"))
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("模板名称为 1 至 100 字")
        key = data.get("id")
        if key is not None and (not isinstance(key, str) or len(key) != 32):
            raise ValueError("模板 ID 无效")
        stamp = datetime.now(UTC).isoformat()
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if key:
                old = db.execute("SELECT version FROM templates WHERE id=?", (key,)).fetchone()
                if old is None:
                    raise KeyError(key)
                if type(data.get("version")) is not int or old["version"] != data["version"]:
                    raise Conflict("模板已被其他页面修改，请另存为新模板，或重新打开后编辑")
                version = old["version"] + 1
                db.execute(
                    "UPDATE templates SET name=?,version=?,updated=?,document=? WHERE id=?",
                    (name.strip(), version, stamp, json.dumps(doc, ensure_ascii=False), key),
                )
            else:
                key = uuid.uuid4().hex
                version = 1
                db.execute(
                    "INSERT INTO templates VALUES (?,?,?,?,?)",
                    (key, name.strip(), version, stamp, json.dumps(doc, ensure_ascii=False)),
                )
        return dict(id=key, name=name.strip(), version=version, updated=stamp, document=doc)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # A detached local server must keep serving if its terminal is closed.
        try:
            super().log_message(format, *args)
        except (OSError, ValueError):
            pass

    def reply(self, status, data, kind="application/json; charset=utf-8", filename=None):
        raw = (
            json.dumps(data, ensure_ascii=False).encode()
            if kind.startswith("application/json")
            else data
        )
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(raw)

    def trusted(self):
        host = self.headers.get("Host", "")
        accepted = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        return host in accepted and (not origin or origin == f"http://{host}")

    def do_GET(self):
        if not self.trusted():
            self.reply(403, {"error": "仅允许本机同源访问"})
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/master":
                self.reply(200, master_document())
                return
            if path == "/api/templates":
                self.reply(200, self.server.store.list())
                return
            if path.startswith("/api/templates/"):
                self.reply(200, self.server.store.get(path.rsplit("/", 1)[1]))
                return
            if path == "/api/health":
                self.reply(
                    200, {"engine": "DocxSpec", "storage": "sqlite", "schema": "docxspec-studio-v1",
                          "refresh_fields": getattr(self.server, "refresh_fields", False),
                          "field_engine": getattr(self.server, "field_engine", "mark")}
                )
                return
            # Never expose database, source code, arbitrary paths or directory listings.
            target = ROOT / "index.html" if path == "/" else ROOT / path.lstrip("/")
            allowed = path in ("/", "/index.html", "/app.js") or (
                path.startswith("/icons/")
                and target.resolve().is_relative_to((ROOT / "icons").resolve())
            )
            if not allowed or not target.is_file():
                self.reply(404, {"error": "文件不存在"})
                return
            self.reply(
                200,
                target.read_bytes(),
                mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            )
        except KeyError:
            self.reply(404, {"error": "模板不存在"})

    def do_POST(self):
        if not self.trusted():
            self.reply(403, {"error": "仅允许本机同源访问"})
            return
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.reply(415, {"error": "请求需使用 JSON"})
                return
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                self.reply(413, {"error": "请求不能超过 25 MB"})
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("请求必须为对象")
            path = urlsplit(self.path).path
            if path == "/api/templates":
                self.reply(200, self.server.store.save(data))
            elif path == "/api/validate":
                self.reply(200, validate(data))
            elif path == "/api/render":
                self.reply(
                    200,
                    render_docx(
                        data, field_engine=getattr(self.server, "field_engine", "mark")
                    ),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "docxspec-report.docx",
                )
            else:
                self.reply(404, {"error": "接口不存在"})
        except (ValueError, TypeError) as exc:
            self.reply(400, {"error": str(exc)})
        except KeyError:
            self.reply(404, {"error": "模板不存在"})
        except Conflict as exc:
            self.reply(409, {"error": str(exc)})
        except RuntimeError as exc:
            self.reply(500, {"error": str(exc)})
        except Exception:
            import traceback

            traceback.print_exc()
            self.reply(500, {"error": "生成或保存失败，请查看服务日志；当前编辑内容仍保留在页面"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4175)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("DOCXSPEC_STUDIO_DATA", ROOT / ".data")),
    )
    fields = parser.add_mutually_exclusive_group()
    fields.add_argument("--field-engine", choices=("mark", "word", "wps", "libreoffice"), default="mark")
    fields.add_argument(
        "--refresh-fields",
        action="store_true",
        help="Refresh actual DOCX field caches using local Microsoft Word (requires pywin32)",
    )
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.store = Store(args.data_dir / "studio.sqlite3")
    server.field_engine = "word" if args.refresh_fields else args.field_engine
    server.refresh_fields = server.field_engine == "word"
    print(f"DocxSpec Studio: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
