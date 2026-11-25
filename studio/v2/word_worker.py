"""One owned Word instance per conversion. Invoked only in a worker subprocess."""

import json
import sys
from pathlib import Path

from docxspec._word_com import COM_PROG_IDS, close_word, refresh_document_fields


def main():
    import psutil
    import pythoncom
    import win32com.client
    import win32process

    engine = sys.argv[1]
    root = Path(sys.argv[2])
    pythoncom.CoInitialize()
    word = doc = None
    try:
        previous_pids = set(psutil.pids())
        instance = win32com.client.DispatchEx(COM_PROG_IDS[engine])
        pid = win32process.GetWindowThreadProcessId(instance.Hwnd)[1]
        if not pid or pid in previous_pids:
            raise RuntimeError("无法确认 Office 启动了独立实例，已停止本次预览")
        word = instance
        ownership = root / "owned-word.tmp"
        ownership.write_text(
            json.dumps({"pid": pid, "created": psutil.Process(pid).create_time()})
        )
        ownership.replace(root / "owned-word.json")
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3
        doc = word.Documents.Open(str(root / "source.docx"), ReadOnly=False, AddToRecentFiles=False)
        pages, issues = refresh_document_fields(doc)
        doc.ExportAsFixedFormat(str(root / "report.pdf"), 17)
        save = doc.SaveAs if engine == "wps" else doc.SaveAs2
        save(str(root / "report.docx"), 12)  # wdFormatXMLDocument
        (root / "engine.json").write_text(
            json.dumps({"version": str(word.Version), "pages": pages, "field_issues": issues}),
            encoding="utf-8",
        )
    finally:
        close_word(doc, word, pythoncom.CoUninitialize)


if __name__ == "__main__":
    main()
