# -*- coding: utf-8 -*-
"""
Word API 示例脚本。
"""

from __future__ import annotations

from pathlib import Path

from .word_api import WordAPI
from .word_styles import (
    BODY_STYLE,
    CAPTION_STYLE,
    MAIN_STYLE,
    TABLE_BODY_STYLE,
    TABLE_HEADER_STYLE,
    make_rich_text,
    make_table_style,
)


def run(output_path=None) -> None:
    """执行示例报告生成流程。"""
    project_root = Path(__file__).resolve().parents[1]
    template_path = project_root / "docxspec" / "templates" / "default_template.docx"
    image_path = project_root / "docxspec" / "templates" / "docxspec.png"
    if output_path is None:
        output_dir = "."

    api = WordAPI(str(template_path))

    text_value = make_rich_text(
        "这是通过普通标签替换进去的一段文字。",
        BODY_STYLE,
    )

    image_container = api.new_container()
    image_container.add_image(
        str(image_path),
        width_cm=8.0,
        align="center",
    )

    table_container = api.new_container()
    table_container.add_table_by_config(
        {
            "data": [
                ["标题", "数据"],
                ["图片", str(image_path)],
                ["数值1", "1e-10"],
                ["数值2", "1e-10"],
            ],
        }
    )

    result_container = api.new_container()
    result_container.add_title("测试报告", MAIN_STYLE)
    result_container.add_paragraph(
        "这是一个容器示例。容器中可以连续加入标题、正文、表格、题注和图片，用于生成完整报告片段。",
        BODY_STYLE,
    )
    result_container.add_paragraph("下面插入一个表格：", BODY_STYLE)
    result_container.add_table_caption_auto("容器内的复合情况表格", CAPTION_STYLE)
    table_style = make_table_style(
        col_widths_cm=(4.0, 10.0),
        row_heights_cm=(0.6, 4.0, 1.0, 1.0),
        image_width_cm=8.0,
    )
    result_container.add_table_by_config(
        {
            "style": {
                "header": TABLE_HEADER_STYLE,
                "body": TABLE_BODY_STYLE,
                "table": table_style,
            },
            "data": [
                ["标题", "数据"],
                ["图片", str(image_path)],
                ["数值1", "1e-10"],
                ["数值2", "1e-10"],
            ],
        }
    )
    result_container.add_paragraph("下面再插入一张独立图片：", BODY_STYLE)
    result_container.add_image(
        str(image_path),
        width_cm=8.0,
        align="center",
    )
    result_container.add_figure_caption_auto("容器内的独立图片", CAPTION_STYLE)

    context = {
        "text_tag": text_value,
        "image_tag": image_container.subdoc,
        "table_tag": table_container.subdoc,
        "result": result_container.subdoc,
    }

    output_path = api.render(
        context=context,
        output_path=f"{output_dir}/demo_output.docx",
    )

    api.write_header_footer(
        docx_path=output_path,
        header_text="这是一段页眉示例",
    )

    print(f"生成完成：{output_path}")
    print("提示：如果页码或编号未刷新，请在 Word 中 Ctrl+A 后按 F9 更新域。")


# if __name__ == "__main__":
#     run()
