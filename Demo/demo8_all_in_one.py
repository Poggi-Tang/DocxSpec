from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
IMAGE_PATH = DEMO_DIR / "docxspec.png"
OUTPUT_PATH = DEMO_DIR / "output" / "demo8_all_in_one_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))

    image_tag = api.new_container()
    image_tag.add_image(str(IMAGE_PATH), width_cm=6.0, align="center")

    table_tag = api.new_container()
    table_tag.add_table(
        [
            ["类型", "接口", "说明"],
            ["文字", "make_rich_text()", "用于 text_tag 这种纯文字占位"],
            ["图片", "add_image()", "用于图片块"],
            ["表格", "add_table()", "用于二维数据渲染"],
        ]
    )

    result = api.new_container()
    result.add_title("Demo8：综合示例")
    result.add_heading("段落", level=1)
    result.add_paragraph("这一节演示容器里的普通段落。")
    result.add_heading("图片和图题注", level=1)
    result.add_image(str(IMAGE_PATH), width_cm=8.0, align="center")
    result.add_figure_caption_auto("综合示例图片")
    result.add_heading("表格和表题注", level=1)
    result.add_table_caption_auto("综合示例表")
    result.add_table(
        [
            ["字段", "值"],
            ["模板", "template.docx"],
            ["图片", "docxspec.png"],
            ["输出", "Demo/output/"],
        ]
    )
    result.add_page_break()
    result.add_heading("分页后的内容", level=1)
    result.add_paragraph("这里说明 add_page_break() 后仍然可以继续追加内容。")

    context = {
        "text_tag": make_rich_text("Demo8：全部能力组合示例。", BODY_STYLE),
        "image_tag": image_tag.subdoc,
        "table_tag": table_tag.subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    api.write_header_footer(str(OUTPUT_PATH), header_text="DocxSpec All In One Demo")
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
