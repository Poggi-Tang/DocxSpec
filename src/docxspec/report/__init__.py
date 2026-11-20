"""Portable Studio-compatible DOCX report templates.

Install the optional `docxspec[report]` dependencies to use this module.
"""

try:
    from ._models import DocumentModel, Node, Page, Style
except ImportError as exc:
    if exc.name != "pydantic":
        raise
    raise ImportError('Install report dependencies with pip install "docxspec[report]".') from exc

from ._bundle import (  # noqa: E402
    BUNDLE_FORMAT,
    TemplateBundle,
    export_template_bundle,
    load_template_bundle,
    register_report_asset,
    render_report,
)

__all__ = [
    "BUNDLE_FORMAT",
    "DocumentModel",
    "Node",
    "Page",
    "Style",
    "TemplateBundle",
    "export_template_bundle",
    "load_template_bundle",
    "register_report_asset",
    "render_report",
]
