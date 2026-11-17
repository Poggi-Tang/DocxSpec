"""One owned Word instance per conversion. Invoked only in a worker subprocess."""

import json
import sys
from pathlib import Path


def main():
    import psutil
    import pythoncom
    import win32com.client
    import win32process

    root = Path(sys.argv[1])
    pythoncom.CoInitialize()
    word = doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        pid = win32process.GetWindowThreadProcessId(word.Hwnd)[1]
        (root / "owned-word.json").write_text(
            json.dumps({"pid": pid, "created": psutil.Process(pid).create_time()})
        )
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3
        doc = word.Documents.Open(str(root / "source.docx"), ReadOnly=False, AddToRecentFiles=False)
        previous = None
        for _attempt in range(3):
            doc.Repaginate()
            for story in doc.StoryRanges:
                current = story
                while current is not None:
                    result = current.Fields.Update()
                    if result not in (None, 0):
                        raise RuntimeError("Story field update failed")
                    current = current.NextStoryRange
            for shapes in [doc.Shapes] + [
                h.Shapes
                for section in doc.Sections
                for h in list(section.Headers) + list(section.Footers)
            ]:
                for shape in shapes:
                    if shape.TextFrame.HasText:
                        result = shape.TextFrame.TextRange.Fields.Update()
                        if result not in (None, 0):
                            raise RuntimeError("Text box field update failed")
            for toc in doc.TablesOfContents:
                toc.Update()
            for toc in doc.TablesOfFigures:
                toc.Update()
            doc.Repaginate()
            signature = (doc.ComputeStatistics(2), tuple(f.Result.Text for f in doc.Fields))
            if signature == previous:
                break
            previous = signature
        else:
            raise RuntimeError("Fields/pagination did not stabilize in three passes")
        doc.SaveAs2(str(root / "report.docx"), FileFormat=16)
        doc.ExportAsFixedFormat(str(root / "report.pdf"), 17)
        (root / "engine.json").write_text(json.dumps({"version": str(word.Version)}))
    finally:
        try:
            if doc is not None:
                doc.Close(SaveChanges=False)
        finally:
            try:
                if word is not None:
                    word.Quit()
            finally:
                pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
