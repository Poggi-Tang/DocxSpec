from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
OUTPUT_PATH = DEMO_DIR / "output" / "demo2_container_paragraph_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    result = api.new_container()
    result.add_title("Demo2：容器中添加段落")
    result.add_heading("第一段", level=1)
    result.add_paragraph("容器适合组织一整块复杂内容。")
    result.add_heading("第二段", level=1)
    result.add_paragraph("这里连续添加多个段落，最后统一插入模板中的 result 标签。")
    result.add_paragraph("你也可以继续往这个容器里追加图片、表格、分页符等内容。")

    context = {
        "text_tag": make_rich_text("Demo2：本例主要看 result 容器区域。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
