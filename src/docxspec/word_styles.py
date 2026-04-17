# -*- coding: utf-8 -*-
"""Word 样式定义。

本模块集中管理 Word 生成过程中使用的样式对象，包含：

1. 文本样式 :class:`TextStyle`
2. 表格单元格样式 :class:`CellStyle`
3. 表格整体样式 :class:`TableStyle`
4. ``docxtpl.RichText`` 辅助构造方法

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from docxtpl import RichText

DEFAULT_FONT_NAME = "宋体"

FONT_SIZE_MAP: dict[str, float] = {
    "初号": 42.0,
    "小初": 36.0,
    "一号": 26.0,
    "小一": 24.0,
    "二号": 22.0,
    "小二": 18.0,
    "三号": 16.0,
    "小三": 15.0,
    "四号": 14.0,
    "小四": 12.0,
    "五号": 10.5,
    "小五": 9.0,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5.0,
}


@dataclass(slots=True)
class TextStyle:
    """文本样式定义。"""

    style_name: Optional[str] = None
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    font_color: Optional[str] = None
    bg_color: Optional[str] = None
    align: Optional[str] = None
    line_spacing: Optional[float] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None
    first_line_indent_chars: Optional[float] = None


@dataclass(slots=True)
class CellStyle:
    """表格单元格样式定义。"""

    paragraph_style_name: Optional[str] = None
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    font_color: Optional[str] = None
    bg_color: Optional[str] = None
    align: Optional[str] = None
    vertical_align: str = "center"
    line_spacing: Optional[float] = None


@dataclass(slots=True)
class TableStyle:
    """表格整体样式定义。"""

    align: str = "center"
    border_color: str = "000000"
    border_size: str = "8"
    col_widths_cm: Optional[Sequence[float]] = None
    row_heights_cm: Optional[Sequence[Optional[float]]] = None
    exact_row_height: bool = False
    header_rows: int = 1
    auto_fit_image: bool = True
    image_width_cm: float = 8.0
    image_margin_cm: float = 0.1
    auto_total_width_cm: float = 14.0
    auto_min_col_width_cm: float = 2.5
    auto_max_col_width_cm: Optional[float] = None


FontSizeInput = Optional[str | int | float]


def resolve_font_size(font_size: FontSizeInput) -> Optional[float]:
    """将字号定义转换为 pt 值。"""
    if font_size is None:
        return None

    if isinstance(font_size, (int, float)):
        return float(font_size)

    if isinstance(font_size, str):
        value = font_size.strip()
        if value in FONT_SIZE_MAP:
            return FONT_SIZE_MAP[value]
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"不支持的字号定义: {font_size}") from exc

    raise TypeError(f"不支持的字号类型: {type(font_size)!r}")


def pt_to_richtext_size(pt_value: float) -> int:
    """将 pt 字号转换为 ``docxtpl.RichText`` 所需的 half-point 值。"""
    return int(round(float(pt_value) * 2))


def make_text_style(
    style_name: Optional[str] = None,
    font_name: Optional[str] = None,
    font_size: FontSizeInput = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    font_color: Optional[str] = None,
    bg_color: Optional[str] = None,
    align: Optional[str] = None,
    line_spacing: Optional[float] = None,
    space_before_pt: Optional[float] = None,
    space_after_pt: Optional[float] = None,
    first_line_indent_chars: Optional[float] = None,
) -> TextStyle:
    """创建 :class:`TextStyle` 对象。"""
    return TextStyle(
        style_name=style_name,
        font_name=font_name,
        font_size=resolve_font_size(font_size),
        bold=bold,
        italic=italic,
        font_color=font_color,
        bg_color=bg_color,
        align=align,
        line_spacing=line_spacing,
        space_before_pt=space_before_pt,
        space_after_pt=space_after_pt,
        first_line_indent_chars=first_line_indent_chars,
    )


def make_cell_style(
    paragraph_style_name: Optional[str] = None,
    font_name: Optional[str] = None,
    font_size: FontSizeInput = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    font_color: Optional[str] = None,
    bg_color: Optional[str] = None,
    align: Optional[str] = None,
    vertical_align: str = "center",
    line_spacing: Optional[float] = None,
) -> CellStyle:
    """创建 :class:`CellStyle` 对象。"""
    return CellStyle(
        paragraph_style_name=paragraph_style_name,
        font_name=font_name,
        font_size=resolve_font_size(font_size),
        bold=bold,
        italic=italic,
        font_color=font_color,
        bg_color=bg_color,
        align=align,
        vertical_align=vertical_align,
        line_spacing=line_spacing,
    )


def make_table_style(
    align: str = "center",
    border_color: str = "000000",
    border_size: str = "8",
    col_widths_cm: Optional[Sequence[float]] = None,
    row_heights_cm: Optional[Sequence[Optional[float]]] = None,
    exact_row_height: bool = False,
    header_rows: int = 1,
    auto_fit_image: bool = True,
    image_width_cm: float = 8.0,
    image_margin_cm: float = 0.1,
    auto_total_width_cm: float = 14.0,
    auto_min_col_width_cm: float = 2.5,
    auto_max_col_width_cm: Optional[float] = None,
) -> TableStyle:
    """创建 :class:`TableStyle` 对象。"""
    return TableStyle(
        align=align,
        border_color=border_color,
        border_size=border_size,
        col_widths_cm=col_widths_cm,
        row_heights_cm=row_heights_cm,
        exact_row_height=exact_row_height,
        header_rows=header_rows,
        auto_fit_image=auto_fit_image,
        image_width_cm=image_width_cm,
        image_margin_cm=image_margin_cm,
        auto_total_width_cm=auto_total_width_cm,
        auto_min_col_width_cm=auto_min_col_width_cm,
        auto_max_col_width_cm=auto_max_col_width_cm,
    )


def make_rich_text(text: Any, style: TextStyle) -> RichText:
    """根据文本样式生成 ``docxtpl.RichText`` 对象。"""
    rich_text = RichText()
    rich_text.add(
        "" if text is None else str(text),
        font=style.font_name or DEFAULT_FONT_NAME,
        size=pt_to_richtext_size(style.font_size or 12.0),
        bold=style.bold,
        italic=style.italic,
        color=style.font_color,
    )
    return rich_text


MAIN_STYLE = make_text_style(
    style_name="KL主标题",
    font_name=DEFAULT_FONT_NAME,
    font_size="二号",
    align="center",
    line_spacing=1.5,
)
Main_STYLE = MAIN_STYLE

H1_STYLE = make_text_style(
    style_name="KL一级标题",
    font_name=DEFAULT_FONT_NAME,
    font_size="小四",
    bold=True,
)

H2_STYLE = make_text_style(
    style_name="KL二级标题",
    font_name=DEFAULT_FONT_NAME,
    font_size="小四",
    bold=True,
)

H3_STYLE = make_text_style(
    style_name="KL其他标题",
    font_name=DEFAULT_FONT_NAME,
    font_size="小四",
    bold=True,
)

BODY_STYLE = make_text_style(
    style_name="KL正文",
    font_name=DEFAULT_FONT_NAME,
    font_size="小四",
    line_spacing=1.5,
    first_line_indent_chars=2,
)

CAPTION_STYLE = make_text_style(
    style_name="KL题注",
    font_name=DEFAULT_FONT_NAME,
    font_size="小四",
    align="center",
    line_spacing=1.5,
)

HEADER_STYLE = make_text_style(
    style_name="KL页眉",
    font_name=DEFAULT_FONT_NAME,
    font_size="五号",
    align="center",
)

FOOTER_STYLE = make_text_style(
    style_name="KL页脚",
    font_name=DEFAULT_FONT_NAME,
    font_size="五号",
    align="center",
)

IMAGE_STYLE = make_text_style(
    style_name="KL图片",
    align="center",
)

TABLE_HEADER_STYLE = make_cell_style(
    paragraph_style_name="KL表格表头",
    font_name=DEFAULT_FONT_NAME,
    font_size="五号",
    align="center",
)

TABLE_BODY_STYLE = make_cell_style(
    paragraph_style_name="KL表格文字",
    font_name=DEFAULT_FONT_NAME,
    font_size="五号",
    align="left",
)

__all__ = [
    "DEFAULT_FONT_NAME",
    "FONT_SIZE_MAP",
    "FontSizeInput",
    "TextStyle",
    "CellStyle",
    "TableStyle",
    "resolve_font_size",
    "pt_to_richtext_size",
    "make_text_style",
    "make_cell_style",
    "make_table_style",
    "make_rich_text",
    "MAIN_STYLE",
    "Main_STYLE",
    "H1_STYLE",
    "H2_STYLE",
    "H3_STYLE",
    "BODY_STYLE",
    "CAPTION_STYLE",
    "HEADER_STYLE",
    "FOOTER_STYLE",
    "IMAGE_STYLE",
    "TABLE_HEADER_STYLE",
    "TABLE_BODY_STYLE",
]
