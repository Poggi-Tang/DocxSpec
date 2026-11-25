"""Locate and run an optional LibreOffice UNO field updater."""

import json
import os
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path


def uno_command(source, output, *, pdf=None, program=None):
    program = (
        program
        or os.environ.get("DOCXSPEC_SOFFICE")
        or os.environ.get("STUDIO_SOFFICE")
        or shutil.which("soffice")
        or shutil.which("libreoffice")
    )
    if program is None:
        return None
    configured = os.environ.get("DOCXSPEC_UNO_PYTHON")
    sibling = Path(program).with_name("python.exe" if os.name == "nt" else "python")
    candidates = (configured,) if configured else (sys.executable, str(sibling), "/usr/bin/python3")
    for python in dict.fromkeys(candidates):
        if python is None or not shutil.which(python):
            continue
        try:
            probe = subprocess.run(
                [python, "-c", "import uno"], capture_output=True, timeout=5, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            return [
                python,
                str(Path(__file__).with_name("_uno_worker.py")),
                str(program),
                str(source),
                str(output),
                str(pdf) if pdf is not None else "",
            ]
    return None


def uno_pages(output):
    return int(json.loads(output.strip().splitlines()[-1])["pages"])


def update_with_libreoffice(source, output):
    command = uno_command(source, output)
    if command is None:
        raise RuntimeError("需要 LibreOffice 和可导入 uno 的 Python，请检查 DOCXSPEC_UNO_PYTHON")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=os.name != "nt",
    )
    try:
        data, error = process.communicate(timeout=120)
    except BaseException as exc:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        else:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise RuntimeError("LibreOffice 刷域超时") from exc
        raise
    if process.returncode or not output.is_file():
        raise RuntimeError("LibreOffice 刷域失败：" + (error or data)[-1500:])
    return uno_pages(data)
