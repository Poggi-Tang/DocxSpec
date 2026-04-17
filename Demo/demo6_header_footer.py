from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
OUTPUT_PATH = DEMO_DIR / "output" / "demo6_header_footer_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    result = api.new_container()
    result.add_title("Demo6：页眉页脚")
    result.add_paragraph("这个示例重点不是容器内容，而是 render 之后的页眉页脚写入。")
    result.add_paragraph("执行顺序：先 render，再 write_header_footer。")

    context = {
        "text_tag": make_rich_text("Demo6：页眉页脚示例。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    api.write_header_footer(
        str(OUTPUT_PATH),
        header_text="DocxSpec Demo Header",
    )
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
