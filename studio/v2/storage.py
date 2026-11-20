# ruff: noqa: E501
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .models import uid


def stamp():
    return datetime.now(UTC).isoformat()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "assets").mkdir(exist_ok=True)
        (root / "renders").mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sets(id TEXT PRIMARY KEY,name TEXT NOT NULL,engine TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY,set_id TEXT NOT NULL,name TEXT NOT NULL,version INTEGER NOT NULL,document TEXT NOT NULL,data TEXT NOT NULL,updated TEXT NOT NULL,archived INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS revisions(template_id TEXT,version INTEGER,document TEXT,data TEXT,name TEXT,updated TEXT,PRIMARY KEY(template_id,version));
            CREATE TABLE IF NOT EXISTS components(id TEXT PRIMARY KEY,set_id TEXT,name TEXT,version INTEGER,node TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT,payload TEXT,result TEXT,error TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS conversion_review_marks(
                template_id TEXT NOT NULL,item_index INTEGER NOT NULL,PRIMARY KEY(template_id,item_index));
            """)
            db.execute(
                "UPDATE jobs SET status='failed',error='服务已重启，请重新生成' WHERE status IN ('queued','compiling','rendering','analyzing')"  # noqa: E501
            )

    def db(self):
        # Use a managed transaction and explicitly close the SQLite connection on Windows.
        from contextlib import contextmanager

        @contextmanager
        def connection():
            with closing(sqlite3.connect(self.root / "studio-v2.sqlite3", timeout=20)) as db:
                db.row_factory = sqlite3.Row
                with db:
                    yield db

        return connection()

    def list_sets(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM sets ORDER BY rowid")]

    def create_set(self, name, engine):
        key = uid()
        with self.db() as db:
            db.execute("INSERT INTO sets VALUES(?,?,?)", (key, name, engine))
        return dict(id=key, name=name, engine=engine)

    def templates(self, set_id=None):
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,set_id,name,version,updated,archived FROM templates WHERE archived=0 AND (? IS NULL OR set_id=?) ORDER BY updated DESC",  # noqa: E501
                    (set_id, set_id),
                )
            ]

    @staticmethod
    def _template(db, key):
        row = db.execute("SELECT * FROM templates WHERE id=?", (key,)).fetchone()
        if not row:
            raise KeyError("模板不存在")
        return {
            **dict(row),
            "document": json.loads(row["document"]),
            "data": json.loads(row["data"]),
        }

    def get_template(self, key):
        with self.db() as db:
            return self._template(db, key)

    def save_template(self, key, body):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._save_template(db, key, body)

    def _save_template(self, db, key, body):
        if not db.execute("SELECT id FROM sets WHERE id=?", (body.set_id,)).fetchone():
            raise KeyError("模板集不存在")
        if key:
            old = db.execute("SELECT version FROM templates WHERE id=?", (key,)).fetchone()
            if not old:
                raise KeyError("模板不存在")
            if old["version"] != body.version:
                raise Conflict("模板已被其他窗口修改，请另存或重新打开")
            version = old["version"] + 1
        else:
            key = uid()
            version = 1
        doc = json.dumps(body.document.model_dump(), ensure_ascii=False)
        data = json.dumps(body.data, ensure_ascii=False)
        now = stamp()
        db.execute(
            "INSERT INTO templates VALUES(?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET set_id=excluded.set_id,name=excluded.name,version=excluded.version,document=excluded.document,data=excluded.data,updated=excluded.updated",  # noqa: E501
            (key, body.set_id, body.name, version, doc, data, now),
        )
        db.execute(
            "INSERT INTO revisions VALUES(?,?,?,?,?,?)",
            (key, version, doc, data, body.name, now),
        )
        return self._template(db, key)

    def revisions(self, key):
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT version,name,updated FROM revisions WHERE template_id=? ORDER BY version DESC",  # noqa: E501
                    (key,),
                )
            ]

    def get_revision(self, key, version):
        with self.db() as db:
            r = db.execute(
                "SELECT * FROM revisions WHERE template_id=? AND version=?", (key, version)
            ).fetchone()
            if not r:
                raise KeyError("版本不存在")
            return {**dict(r), "document": json.loads(r["document"]), "data": json.loads(r["data"])}

    @staticmethod
    def _conversion_result(db, key):
        if not db.execute("SELECT 1 FROM templates WHERE id=?", (key,)).fetchone():
            raise KeyError("模板不存在")
        # Completed jobs persist the original mapping, including for existing drafts.
        row = db.execute(
            """SELECT result FROM jobs
               WHERE status='ready' AND json_extract(result, '$.template_id')=?
               ORDER BY rowid DESC LIMIT 1""",
            (key,),
        ).fetchone()
        return json.loads(row["result"]) if row else None

    @staticmethod
    def _reviewed_indices(db, key):
        return [
            row["item_index"]
            for row in db.execute(
                """SELECT item_index FROM conversion_review_marks
                   WHERE template_id=? ORDER BY item_index""",
                (key,),
            )
        ]

    def conversion_review(self, key):
        with self.db() as db:
            result = self._conversion_result(db, key)
            if result is None:
                return None
            return {
                "template_id": key,
                "review": result.get("review", []),
                "source_blocks": result.get("source_blocks", []),
                "reviewed_indices": self._reviewed_indices(db, key),
            }

    def mark_conversion_review(self, key, index, reviewed):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            result = self._conversion_result(db, key)
            if result is None or not 0 <= index < len(result.get("review", [])):
                raise KeyError("审核项不存在")
            if reviewed:
                db.execute(
                    "INSERT OR IGNORE INTO conversion_review_marks VALUES(?,?)", (key, index)
                )
            else:
                db.execute(
                    "DELETE FROM conversion_review_marks WHERE template_id=? AND item_index=?",
                    (key, index),
                )
            return {"reviewed_indices": self._reviewed_indices(db, key)}

    def components(self, set_id):
        with self.db() as db:
            return [
                {**dict(r), "node": json.loads(r["node"])}
                for r in db.execute("SELECT * FROM components WHERE set_id=?", (set_id,))
            ]

    def create_component(self, set_id, name, node):
        key = uid()
        with self.db() as db:
            if not db.execute("SELECT 1 FROM sets WHERE id=?", (set_id,)).fetchone():
                raise KeyError("模板集不存在")
            db.execute(
                "INSERT INTO components VALUES(?,?,?,?,?)", (key, set_id, name, 1, json.dumps(node))
            )
        return dict(id=key, set_id=set_id, name=name, version=1, node=node)

    def new_job(self, payload):
        key = uid()
        with self.db() as db:
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?)",
                (key, "queued", json.dumps(payload), None, None, stamp()),
            )
        return key

    def job(self, key):
        with self.db() as db:
            r = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
            if not r:
                raise KeyError("任务不存在")
            return {
                **dict(r),
                "payload": json.loads(r["payload"]),
                "result": json.loads(r["result"]) if r["result"] else None,
            }

    def update_job(self, key, status, result=None, error=None):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status=?,result=?,error=? WHERE id=? AND status<>'cancelled'",
                (status, json.dumps(result) if result else None, error, key),
            )

    def complete_conversion_job(self, key, template_body, result):
        """Publish the template and its review together if cancellation has not won."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT status FROM jobs WHERE id=?", (key,)).fetchone()
            if job is None:
                raise KeyError("任务不存在")
            if job["status"] != "analyzing":
                return
            template = self._save_template(db, None, template_body)
            db.execute(
                "UPDATE jobs SET status='ready',result=?,error=NULL WHERE id=?",
                (json.dumps({**result, "template_id": template["id"]}), key),
            )

    def cancel_job(self, key):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status='cancelled' WHERE id=? AND status IN ('queued','compiling','rendering','analyzing')",  # noqa: E501
                (key,),
            )
