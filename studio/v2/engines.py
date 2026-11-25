"""Isolated Office subprocesses. No engine substitution is performed."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryFile

import psutil
import pymupdf as fitz


class RenderCancelled(Exception):
    """The caller has cancelled this preview."""


def capabilities():
    word = sys.platform == "win32" and importlib.util.find_spec("win32com") is not None
    lo = os.environ.get("STUDIO_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
    return [
        dict(
            id="word",
            name="Microsoft Word",
            available=word,
            reason="需要 Windows、已安装的 Word 和 pywin32；启动时仍需验证",
        ),
        dict(
            id="wps",
            name="WPS",
            available=False,
            reason="此版本尚无经过验证的 WPS 自动化适配器，请在 WPS 手工检查",
        ),
        dict(
            id="libreoffice",
            name="LibreOffice",
            available=bool(lo and Path(lo).is_file()),
            reason="真实 LibreOffice 排版，不代表 Word/WPS；设置 STUDIO_SOFFICE 可指定程序",
        ),
    ]


def _stop_office(process, owner_file):
    if process.poll() is None:
        with suppress(psutil.Error):
            children = psutil.Process(process.pid).children(recursive=True)
            for child in reversed(children):
                with suppress(psutil.Error):
                    child.kill()
        with suppress(OSError):
            process.kill()
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=2)
    if owner_file is not None:
        # A COM server can be launched outside the worker's process tree.
        with suppress(OSError, ValueError, KeyError, TypeError, psutil.Error):
            owner = json.loads(owner_file.read_text())
            word = psutil.Process(owner["pid"])
            if word.create_time() == owner["created"]:
                word.kill()


def _tail(stream):
    size = stream.seek(0, os.SEEK_END)
    stream.seek(max(0, size - 6000))
    return stream.read().decode(errors="replace")[-1500:]


def _run_office(command, *, check_cancelled, timeout, owner_file=None):
    # Files avoid waiting for pipe handles inherited by Office subprocesses.
    with TemporaryFile() as output, TemporaryFile() as errors:
        if check_cancelled is not None:
            check_cancelled()
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"} if owner_file is not None else None
        process = subprocess.Popen(command, stdout=output, stderr=errors, env=env)
        try:
            deadline = time.monotonic() + timeout
            while True:
                if check_cancelled is not None:
                    check_cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    process.wait(timeout=min(0.2, remaining) if check_cancelled else remaining)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if check_cancelled is not None:
                check_cancelled()
        except BaseException:
            _stop_office(process, owner_file)
            raise
        if process.returncode and owner_file is not None:
            _stop_office(process, owner_file)
        return process.returncode, _tail(output), _tail(errors)


def _page_mapping(pdf, anchors, check_cancelled):
    mapping = []
    normalized_text = None
    for anchor in anchors:
        if check_cancelled is not None:
            check_cancelled()
        text = anchor["text"].strip()
        if not text:
            continue
        if normalized_text is None:
            normalized_text = "".join("".join(page.get_text().split()) for page in pdf)
        # Only offer a page selection for text occurring exactly once in the PDF.
        if normalized_text.count("".join(text.split())) != 1:
            continue
        matches = []
        for i, page in enumerate(pdf):
            rects = page.search_for(text)
            if rects:
                matches.append((i, rects))
        if len(matches) == 1:
            page, rects = matches[0]
            mapping.append(
                {
                    **anchor,
                    "page": page,
                    "rects": [list(r) for r in rects],
                    "method": "unique-pdf-text",
                }
            )
    return mapping


def render(root: Path, engine: str, anchors, *, check_cancelled: Callable[[], None] | None = None):
    if not any(c["id"] == engine and c["available"] for c in capabilities()):
        raise ValueError("所选排版引擎不可用；没有自动切换到其他引擎")
    source = root / "source.docx"
    final = root / "report.docx"
    owned_word = None
    if engine == "word":
        owned_word = root / "owned-word.json"
        cmd = [sys.executable, str(Path(__file__).with_name("word_worker.py")), str(root)]
    else:
        program = (
            os.environ.get("STUDIO_SOFFICE")
            or shutil.which("soffice")
            or shutil.which("libreoffice")
        )
        shutil.copy2(source, final)
        cmd = [
            program,
            "--headless",
            "-env:UserInstallation=" + (root / "profile").as_uri(),
            "--convert-to",
            "pdf",
            "--outdir",
            str(root),
            str(final),
        ]
    try:
        code, out, err = _run_office(
            cmd, check_cancelled=check_cancelled, timeout=120, owner_file=owned_word
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Office 渲染超时，已停止本次任务") from None
    if code or not (root / "report.pdf").is_file():
        raise RuntimeError("排版失败：" + (err or out or "排版引擎未生成 PDF"))
    if check_cancelled is not None:
        check_cancelled()
    with fitz.open(root / "report.pdf") as pdf:
        mapping = _page_mapping(pdf, anchors, check_cancelled)
        page_sizes = [[p.rect.width, p.rect.height] for p in pdf]
    result = dict(
        engine=engine,
        pages=len(page_sizes),
        page_sizes=page_sizes,
        mapping=mapping,
        hashes={
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("report.docx", "report.pdf")
        },
        field_status="Word field and directory results stabilized across inspected stories"
        if engine == "word"
        else "LibreOffice PDF rendered; DOCX field caches are not certified refreshed",
        notes=[
            "只有唯一文本匹配提供页面选择；其他对象请使用结构树。",
            "缺字体可能导致替代，请在交付机器核对字体。",
        ],
    )
    if engine == "word":
        result["engine_version"] = json.loads((root / "engine.json").read_text())["version"]
    else:
        try:
            code, out, _ = _run_office(
                [program, "--version"], check_cancelled=check_cancelled, timeout=10
            )
            result["engine_version"] = out.strip()[:160] if not code else "unknown"
        except (OSError, subprocess.TimeoutExpired):
            result["engine_version"] = "unknown"
    return result
