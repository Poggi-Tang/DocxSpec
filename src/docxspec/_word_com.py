"""Refresh and inspect Word fields across document stories."""

import sys


def _shape_fields(shapes):
    for shape in shapes:
        if shape.Type == 6:  # msoGroup
            yield from _shape_fields(shape.GroupItems)
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
        signature = (
            document.ComputeStatistics(2),  # wdStatisticPages
            tuple(tuple(field.Result.Text for field in fields) for fields, _ in _fields(document)),
            tuple(directory.Range.Text for directory in _directories(document)),
        )
        if signature == previous:
            return
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
