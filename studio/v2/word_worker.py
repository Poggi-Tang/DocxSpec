"""One owned Word instance per conversion. Invoked only in a worker subprocess."""

import json
import sys
from pathlib import Path

from docxspec._word_com import close_word, refresh_document_fields


def main():
    import psutil
    import pythoncom
    import win32com.client
    import win32process

    root = Path(sys.argv[1])
    pythoncom.CoInitialize()
    word = doc = None
    try:
        previous_pids = set(psutil.pids())
        instance = win32com.client.DispatchEx("Word.Application")
        pid = win32process.GetWindowThreadProcessId(instance.Hwnd)[1]
        if pid in previous_pids:
            raise RuntimeError("Word did not start an isolated process for this preview")
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
        refresh_document_fields(doc)
        doc.SaveAs2(str(root / "report.docx"), FileFormat=16)
        doc.ExportAsFixedFormat(str(root / "report.pdf"), 17)
        (root / "engine.json").write_text(json.dumps({"version": str(word.Version)}))
    finally:
        close_word(doc, word, pythoncom.CoUninitialize)


if __name__ == "__main__":
    main()
