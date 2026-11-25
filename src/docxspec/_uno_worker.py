"""Run LibreOffice with its Python UNO bindings in an isolated profile."""

import json
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import uuid4


def _desktop(program, profile):
    import uno
    from com.sun.star.connection import NoConnectException

    pipe = f"docxspec_{uuid4().hex}"
    # Some UNO imports set URE_BOOTSTRAP through putenv for the Python client.
    # Give the server an explicit environment so it can load its own registry.
    env = dict(os.environ)
    env.pop("URE_BOOTSTRAP", None)
    process = subprocess.Popen(
        [
            program,
            "--headless",
            "--norestore",
            "-env:UserInstallation=" + profile.as_uri(),
            f"--accept=pipe,name={pipe};urp;StarOffice.ServiceManager",
        ],
        env=env,
    )
    deadline = monotonic() + 15
    try:
        context = uno.getComponentContext()
        resolver = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", context
        )
        while process.poll() is None and monotonic() < deadline:
            try:
                remote = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                desktop = remote.ServiceManager.createInstanceWithContext(
                    "com.sun.star.frame.Desktop", remote
                )
                return process, desktop
            except NoConnectException:
                sleep(0.1)
        raise RuntimeError("无法启动 LibreOffice UNO 连接")
    except BaseException:
        _stop(process)
        raise


def _stop(process):
    if process.poll() is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _property(name, value):
    from com.sun.star.beans import PropertyValue

    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def _refresh(document):
    indexes = list(document.getDocumentIndexes())
    previous = None
    for _ in range(3):
        document.getTextFields().refresh()
        for index in indexes:
            index.update()
        document.getTextFields().refresh()
        cursor = document.getCurrentController().getViewCursor()
        cursor.jumpToLastPage()
        pages = cursor.getPage()
        signature = pages, tuple(index.getAnchor().getString() for index in indexes)
        if signature == previous:
            return pages
        previous = signature
    raise RuntimeError("LibreOffice 目录或分页在三轮更新后仍未稳定")


def main():
    program, source, output, pdf = sys.argv[1:]
    output = Path(output).resolve()
    with TemporaryDirectory(prefix="docxspec-uno-", dir=output.parent) as folder:
        process, desktop = _desktop(program, Path(folder))
        document = None
        try:
            document = desktop.loadComponentFromURL(
                Path(source).resolve().as_uri(),
                "_blank",
                0,
                (
                    _property("Hidden", True),
                    _property("MacroExecutionMode", 0),
                    _property("UpdateDocMode", 0),
                ),
            )
            if document is None:
                raise RuntimeError("LibreOffice 无法打开 DOCX")
            pages = _refresh(document)
            document.getCurrentController().getViewCursor().jumpToFirstPage()
            if pdf:
                document.storeToURL(
                    Path(pdf).resolve().as_uri(), (_property("FilterName", "writer_pdf_Export"),)
                )
            document.storeAsURL(output.as_uri(), (_property("FilterName", "Office Open XML Text"),))
            print(json.dumps({"pages": pages}), flush=True)
        finally:
            if document is not None:
                with suppress(Exception):
                    document.close(True)
            with suppress(Exception):
                desktop.terminate()
            _stop(process)


if __name__ == "__main__":
    main()
