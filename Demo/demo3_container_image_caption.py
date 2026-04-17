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
OUTPUT_PATH = DEMO_DIR / "output" / "demo3_container_image_caption_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    result = api.new_container()
    result.add_title("Demo3：容器中添加图片和图题注")
    result.add_paragraph("下面的内容通过容器插入，而不是直接走 image_tag。")
    result.add_image(str(IMAGE_PATH), width_cm=8.0, align="center")
    result.add_figure_caption_auto("DocxSpec 示例图片")

    context = {
        "text_tag": make_rich_text("Demo3：容器中图片 + 图题注。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
