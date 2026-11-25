"""Public exports for docxspec."""

from docx.oxml.ns import nsmap as _docx_nsmap

from ._field_audit import FieldVerification, verify_docx_fields
from ._section_templates import DEFAULT_DS_SECTIONS
from .kl_standard import (
    DEFAULT_MASTER_TEMPLATE,
    build_standard_docx,
    check_word_standard,
    classify_docx_body,
    classify_heading,
    clean_heading_number,
    detect_source_front_matter,
)
from .template_styles import ensure_ds_styles
from .word_api import BlockTemplate, DocContainer, WordAPI
from .word_fields import (
    FieldRefreshResult,
    PartialFieldRefreshError,
    mark_update_fields_on_open,
    normalize_table_list_fields,
    prune_empty_caption_lists,
    refresh_docx_fields,
    refresh_fields_with_word,
)
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

# docxcompose registers its custom-properties prefix in python-docx's shared map.
# Restore the core-properties mapping used by python-docx's metadata setters.
_docx_nsmap["cp"] = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"

__version__ = "0.3.0"

__all__ = [
    "WordAPI",
    "ensure_ds_styles",
    "BlockTemplate",
    "DocContainer",
    "FieldRefreshResult",
    "FieldVerification",
    "PartialFieldRefreshError",
    "DEFAULT_MASTER_TEMPLATE",
    "DEFAULT_DS_SECTIONS",
    "check_word_standard",
    "classify_docx_body",
    "build_standard_docx",
    "clean_heading_number",
    "classify_heading",
    "detect_source_front_matter",
    "mark_update_fields_on_open",
    "normalize_table_list_fields",
    "prune_empty_caption_lists",
    "refresh_docx_fields",
    "refresh_fields_with_word",
    "verify_docx_fields",
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
