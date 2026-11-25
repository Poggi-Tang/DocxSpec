import json
import shutil
import sys
from pathlib import Path
from time import monotonic, sleep

import psutil
import pymupdf
from fastapi.testclient import TestClient

from studio.v2 import app, engines

_WAITING_WORKER = """
import json, os, subprocess, sys, time
from pathlib import Path

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
marker = Path(sys.argv[1])
temp = marker.with_suffix(".tmp")
temp.write_text(json.dumps([os.getpid(), child.pid]))
temp.replace(marker)
time.sleep(30)
"""


def wait_for(check):
    deadline = monotonic() + 8
    while not check():
        assert monotonic() < deadline, "Timed out waiting for preview status"
        sleep(0.05)


def running(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def test_cancel_stops_office_process_tree_and_releases_preview_queue(tmp_path, monkeypatch):
    def capabilities():
        return [{"id": "word", "available": True}]

    monkeypatch.setattr(app, "capabilities", capabilities)
    monkeypatch.setattr(engines, "capabilities", capabilities)
    real_run = engines._run_office
    first = True

    def run_office(command, **kwargs):
        nonlocal first
        root = Path(command[-1])
        if first:
            first = False
            return real_run(
                [sys.executable, "-c", _WAITING_WORKER, str(root / "started.json")], **kwargs
            )
        shutil.copyfile(root / "source.docx", root / "report.docx")
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((24, 24), "Second preview")
            pdf.save(root / "report.pdf")
        (root / "engine.json").write_text('{"version": "test-fixture"}')
        return 0, "", ""

    monkeypatch.setattr(engines, "_run_office", run_office)
    document = {"nodes": [{"id": "body", "kind": "paragraph", "text": "Second preview"}]}
    payload = {"document": document, "data": {}, "engine": "word"}
    with TestClient(app.create_app(tmp_path)) as client:
        initial = client.post("/api/v2/renders", json=payload)
        assert initial.status_code == 200
        key = initial.json()["id"]
        job = f"/api/v2/jobs/{key}"
        marker = tmp_path / "renders" / key / "started.json"
        try:
            wait_for(marker.exists)
            processes = [psutil.Process(pid) for pid in json.loads(marker.read_text())]
            assert all(process.is_running() for process in processes)

            next_job = client.post("/api/v2/renders", json=payload).json()["id"]
            next_path = f"/api/v2/jobs/{next_job}"
            assert client.get(next_path).json()["status"] == "queued"
            assert client.delete(job).json()["status"] == "cancelled"
            wait_for(lambda: client.get(next_path).json()["status"] == "ready")
            wait_for(lambda: not any(running(process) for process in processes))
            assert client.get(job).json()["status"] == "cancelled"
            assert client.get(f"/api/v2/artifacts/{key}/report.pdf").status_code == 404
            assert client.get(f"/api/v2/artifacts/{next_job}/report.pdf").status_code == 200
            assert client.delete(next_path).json()["status"] == "ready"
        finally:
            client.delete(job)
