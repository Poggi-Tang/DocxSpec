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
OUTPUT_PATH = DEMO_DIR / "output" / "demo5_container_table_image_caption_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    result = api.new_container()
    result.add_title("Demo5：表格中添加图片和表题注")
    result.add_paragraph("当表格单元格内容是有效图片路径时，库会自动插入图片。")
    result.add_table(
        [
            ["图片", "名称", "说明"],
            [str(IMAGE_PATH), "DocxSpec", "这一格会自动渲染为图片"],
            ["普通文本", "第二行", "这一格保持普通字符串"],
        ]
    )
    result.add_table_caption_auto("带图片单元格的表格")

    context = {
        "text_tag": make_rich_text("Demo5：表格中插图。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
