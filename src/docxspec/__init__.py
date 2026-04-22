# -*- coding: utf-8 -*-
"""Public exports for docxspec."""

from .word_api import DocContainer, WordAPI
from .word_styles import (
    BODY_STYLE,
    CAPTION_STYLE,
    MAIN_STYLE,
    TABLE_BODY_STYLE,
    TABLE_HEADER_STYLE,
    CellStyle,
    TableStyle,
    TextStyle,
    make_rich_text,
    make_table_style,
)

__version__ = "0.0.3"

__all__ = [
    "WordAPI",
    "DocContainer",
    "TextStyle",
    "CellStyle",
    "TableStyle",
    "BODY_STYLE",
    "CAPTION_STYLE",
    "MAIN_STYLE",
    "TABLE_BODY_STYLE",
    "TABLE_HEADER_STYLE",
    "make_rich_text",
    "make_table_style",
    "__version__",
]
