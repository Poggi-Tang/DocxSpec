from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import WordAPI, make_rich_text, make_table_style
from docxspec.word_styles import (
    BODY_STYLE,
    CAPTION_STYLE,
    FOOTER_STYLE,
    H1_STYLE,
    H2_STYLE,
    H3_STYLE,
    HEADER_STYLE,
    IMAGE_STYLE,
    MAIN_STYLE,
    TABLE_BODY_STYLE,
    TABLE_HEADER_STYLE,
)


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
IMAGE_PATH = DEMO_DIR / "docxspec.png"
OUTPUT_PATH = DEMO_DIR / "output" / "demo7_styles_in_container_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))

    result = api.new_container()
    result.add_paragraph("KL主标题 / MAIN_STYLE", style=MAIN_STYLE)
    result.add_paragraph("KL一级标题 / H1_STYLE", style=H1_STYLE)
    result.add_paragraph("KL二级标题 / H2_STYLE", style=H2_STYLE)
    result.add_paragraph("KL三级标题 / H3_STYLE", style=H3_STYLE)
    result.add_paragraph(
        "KL正文 / BODY_STYLE：这是正文段落示例，用来说明普通内容排版。",
        style=BODY_STYLE,
    )
    result.add_paragraph("下面是 KL图片 / IMAGE_STYLE 对应的图片段落：", style=BODY_STYLE)
    result.add_image(str(IMAGE_PATH), width_cm=6.0, align="center", style=IMAGE_STYLE)
    result.add_paragraph("下面是 KL题注 / CAPTION_STYLE 对应的题注：", style=BODY_STYLE)
    result.add_figure_caption_auto("样式示例图片", style=CAPTION_STYLE)
    result.add_paragraph("下面是 KL表格表头 / KL表格文字 样式示例：", style=BODY_STYLE)
    result.add_table(
        [
            ["样式名", "对象", "说明"],
            ["KL表格表头", "TABLE_HEADER_STYLE", "用于表头单元格"],
            ["KL表格文字", "TABLE_BODY_STYLE", "用于表体单元格"],
        ],
        header_style=TABLE_HEADER_STYLE,
        body_style=TABLE_BODY_STYLE,
        table_style=make_table_style(col_widths_cm=[4.0, 4.0, 6.0]),
    )
    result.add_table_caption_auto("表格样式示例", style=CAPTION_STYLE)
    result.add_paragraph(
        "KL页眉 / HEADER_STYLE 与 KL页脚 / FOOTER_STYLE 不属于正文容器内容，"
        "会在 render 后通过 write_header_footer() 演示。",
        style=BODY_STYLE,
    )

    context = {
        "text_tag": make_rich_text("Demo7：样式示例。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    api.write_header_footer(
        str(OUTPUT_PATH),
        header_text="Demo7 Header Style",
        header_style=HEADER_STYLE,
        footer_style=FOOTER_STYLE,
    )
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
