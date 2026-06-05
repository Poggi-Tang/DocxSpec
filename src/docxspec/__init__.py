"""Public exports for docxspec."""

from .kl_standard import (
    DEFAULT_MASTER_TEMPLATE,
    build_standard_docx,
    check_word_standard,
    classify_docx_body,
    classify_heading,
    clean_heading_number,
    detect_source_front_matter,
)
from .word_api import BlockTemplate, DocContainer, WordAPI
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

__version__ = "0.0.7"

__all__ = [
    "WordAPI",
    "BlockTemplate",
    "DocContainer",
    "DEFAULT_MASTER_TEMPLATE",
    "check_word_standard",
    "classify_docx_body",
    "build_standard_docx",
    "clean_heading_number",
    "classify_heading",
    "detect_source_front_matter",
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
