"""Isolated Office subprocesses. No engine substitution is performed."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf as fitz


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


def render(root: Path, engine: str, anchors):
    import psutil

    if not any(c["id"] == engine and c["available"] for c in capabilities()):
        raise ValueError("所选排版引擎不可用；没有自动切换到其他引擎")
    source = root / "source.docx"
    final = root / "report.docx"
    if engine == "word":
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("word_worker.py")), str(root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        # Kill only this conversion process tree, never unrelated user Office sessions.
        try:
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except psutil.Error:
                    pass
            parent.kill()
        except psutil.Error:
            pass
        proc.communicate()
        if engine == "word" and (root / "owned-word.json").exists():
            owner = json.loads((root / "owned-word.json").read_text())
            try:
                owned = psutil.Process(owner["pid"])
                if owned.create_time() == owner["created"]:
                    owned.kill()
            except psutil.Error:
                pass
        raise RuntimeError("Office 渲染超时，已停止本次任务") from None
    if proc.returncode or not (root / "report.pdf").is_file():
        raise RuntimeError(
            "排版失败：" + (err.decode(errors="replace") or out.decode(errors="replace"))[-1500:]
        )
    pdf = fitz.open(root / "report.pdf")
    mapping = []
    for anchor in anchors:
        text = anchor["text"].strip()
        if not text:
            continue
        matches = []
        for i, page in enumerate(pdf):
            rects = page.search_for(text)
            if rects:
                matches.append((i, rects))

        # Only offer a page selection when text occurs exactly once in extracted document.
        def normalized(s):
            return "".join(s.split())

        alltext = normalized("".join(page.get_text() for page in pdf))
        unique = bool(normalized(text)) and alltext.count(normalized(text)) == 1
        if unique and len(matches) == 1:
            page, rects = matches[0]
            mapping.append(
                {
                    **anchor,
                    "page": page,
                    "rects": [list(r) for r in rects],
                    "method": "unique-pdf-text",
                }
            )
    result = dict(
        engine=engine,
        pages=len(pdf),
        page_sizes=[[p.rect.width, p.rect.height] for p in pdf],
        mapping=mapping,
        hashes={
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("report.docx", "report.pdf")
        },
        field_status="Word worker updated supported document stories; inspect exported results"
        if engine == "word"
        else "LibreOffice PDF rendered; DOCX field caches are not certified refreshed",
        notes=[
            "只有唯一文本匹配提供页面选择；其他对象请使用结构树。",
            "缺字体可能导致替代，请在交付机器核对字体。",
        ],
    )
    pdf.close()
    if engine == "word":
        result["engine_version"] = json.loads((root / "engine.json").read_text())["version"]
    else:
        try:
            result["engine_version"] = (
                subprocess.check_output([program, "--version"], timeout=10).decode().strip()[:160]
            )
        except Exception:
            result["engine_version"] = "unknown"
    return result
