from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
OUTPUT_PATH = DEMO_DIR / "output" / "demo1_paragraph_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    context = {
        "text_tag": make_rich_text("Demo1：这是最简单的文字标签示例。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": api.new_container().subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
