"""Compatibility imports for the report compiler now shared with Python."""

from docxspec.report._compiler import (
    LEVELS,
    TOKEN,
    compile_document,
    expand,
    field,
    fill,
    lookup,
    style_name,
)

__all__ = [
    "LEVELS",
    "TOKEN",
    "compile_document",
    "expand",
    "field",
    "fill",
    "lookup",
    "style_name",
]
