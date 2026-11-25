"""Refresh and inspect Word fields across document stories."""

import importlib.util
import sys

COM_PROG_IDS = {"word": "Word.Application", "wps": "KWPS.Application"}


def com_engine_registered(engine):
    if sys.platform != "win32" or importlib.util.find_spec("win32com") is None:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, COM_PROG_IDS[engine] + r"\CLSID"):
            return True
    except OSError:
        return False


def _shape_fields(shapes):
    for shape in shapes:
        if shape.Type == 6:  # msoGroup
            yield from _shape_fields(shape.GroupItems)
        elif shape.Type == 20:  # msoCanvas
            yield from _shape_fields(shape.CanvasItems)
        elif shape.TextFrame.HasText:
            yield shape.TextFrame.TextRange.Fields, "Text box"


def _fields(document):
    yield document.Fields, "Document"
    for story in document.StoryRanges:
        current = story
        while current is not None:
            if current.StoryType != 1:  # wdMainTextStory is already in document.Fields
                yield current.Fields, "Story"
            current = current.NextStoryRange
    yield from _shape_fields(document.Shapes)
    for section in document.Sections:
        for area in (*section.Headers, *section.Footers):
            yield from _shape_fields(area.Shapes)


def _directories(document):
    yield from document.TablesOfContents
    yield from document.TablesOfFigures


def refresh_document_fields(document):
    """Require two consecutive passes with matching page, field and directory results."""
    previous = None
    for _ in range(3):
        document.Repaginate()
        for fields, area in _fields(document):
            result = fields.Update()
            if result not in (None, 0):
                raise RuntimeError(f"{area} field update failed at field {result}")
        for directory in _directories(document):
            directory.Update()
        document.Repaginate()
        for directory in _directories(document):
            directory.UpdatePageNumbers()
        areas = [(tuple(fields), area) for fields, area in _fields(document)]
        signature = (
            document.ComputeStatistics(2),  # wdStatisticPages
            tuple(tuple(field.Result.Text for field in fields) for fields, _ in areas),
            tuple(directory.Range.Text for directory in _directories(document)),
        )
        if signature == previous:
            locked = []
            for fields, area in areas:
                for field in fields:
                    if getattr(field, "Locked", False):
                        code = getattr(getattr(field, "Code", None), "Text", "").strip()
                        locked.append(f"{area}: {code or 'field'} is locked")
            return signature[0], tuple(dict.fromkeys(locked))
        previous = signature
    raise RuntimeError("Fields/pagination did not stabilize in three passes")


def close_word(document, application, uninitialize):
    """Release COM resources without replacing a failure from opening or refreshing."""
    active_error = sys.exc_info()[1]
    cleanup_errors = []
    for action in (
        (lambda: document.Close(SaveChanges=False)) if document is not None else None,
        (lambda: application.Quit()) if application is not None else None,
        uninitialize,
    ):
        if action is not None:
            try:
                action()
            except Exception as exc:
                cleanup_errors.append(str(exc))
    if cleanup_errors and active_error is None:
        raise RuntimeError("Cleanup failed: " + "; ".join(cleanup_errors))
