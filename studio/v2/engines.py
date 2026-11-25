"""Isolated Office subprocesses. No engine substitution is performed."""

import hashlib
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

from docxspec import refresh_docx_fields, verify_docx_fields
from docxspec._libreoffice_fields import uno_command
from docxspec._word_com import COM_PROG_IDS, com_engine_registered


class RenderCancelled(Exception):
    """The caller has cancelled this preview."""


def capabilities():
    lo = os.environ.get("STUDIO_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
    return [
        dict(
            id="word",
            name="Microsoft Word",
            available=com_engine_registered("word"),
            reason="需要已注册 Word COM 的 Windows 和 pywin32",
        ),
        dict(
            id="wps",
            name="WPS",
            available=com_engine_registered("wps"),
            reason="需要已注册 KWPS.Application 的 Windows 版 WPS 和 pywin32",
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
    pdf_path = root / "report.pdf"
    refresh_docx_fields(source, engine="mark")
    owned_word = None
    updates_docx = True
    if engine in COM_PROG_IDS:
        owned_word = root / "owned-word.json"
        cmd = [sys.executable, str(Path(__file__).with_name("word_worker.py")), engine, str(root)]
    else:
        program = (
            os.environ.get("STUDIO_SOFFICE")
            or shutil.which("soffice")
            or shutil.which("libreoffice")
        )
        cmd = uno_command(source, final, pdf=pdf_path, program=program)
        if cmd is None:
            updates_docx = False
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
    if code or not pdf_path.is_file() or not final.is_file():
        raise RuntimeError("排版失败：" + (err or out or "排版引擎未生成完整产物"))
    if check_cancelled is not None:
        check_cancelled()
    with fitz.open(pdf_path) as pdf:
        mapping = _page_mapping(pdf, anchors, check_cancelled)
        page_sizes = [[p.rect.width, p.rect.height] for p in pdf]
    field_state = "marked_for_update"
    field_status = "仅请求打开时更新 DOCX 的域。LibreOffice 当前只生成 PDF。"
    field_issues = []
    word_info = {}
    if engine in COM_PROG_IDS:
        word_info = json.loads((root / "engine.json").read_text(encoding="utf-8"))
        field_issues.extend(word_info.get("field_issues", ()))
        if "pages" in word_info and word_info["pages"] != len(page_sizes):
            field_issues.append("Office 刷域时的页数和最终 PDF 页数不同")
    if updates_docx:
        field_issues.extend(
            verify_docx_fields(final, original=source, page_count=len(page_sizes)).issues
        )
        if field_issues:
            field_state = "partial"
            field_status = "部分域未通过保存后检查。下载将提供排版前的 DOCX。"
            shutil.copy2(source, final)
        else:
            field_state = "refreshed"
            field_status = "已更新并检查保存后的目录、题注、页码和交叉引用。"
    result = dict(
        engine=engine,
        pages=len(page_sizes),
        page_sizes=page_sizes,
        mapping=mapping,
        hashes={
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("report.docx", "report.pdf")
        },
        field_state=field_state,
        field_status=field_status,
        field_issues=field_issues,
        notes=[
            "只有唯一文本匹配提供页面选择；其他对象请使用结构树。",
            "缺字体可能导致替代，请在交付机器核对字体。",
        ],
    )
    if engine in COM_PROG_IDS:
        result["engine_version"] = word_info["version"]
    else:
        try:
            code, out, _ = _run_office(
                [program, "--version"], check_cancelled=check_cancelled, timeout=10
            )
            result["engine_version"] = out.strip()[:160] if not code else "unknown"
        except (OSError, subprocess.TimeoutExpired):
            result["engine_version"] = "unknown"
    return result
