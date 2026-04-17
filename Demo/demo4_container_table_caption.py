from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text


DEMO_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = DEMO_DIR / "template.docx"
OUTPUT_PATH = DEMO_DIR / "output" / "demo4_container_table_caption_output.docx"


def main() -> Path:
    api = WordAPI(str(TEMPLATE_PATH))
    result = api.new_container()
    result.add_title("Demo4：容器中添加表格和表题注")
    result.add_paragraph("下面这张表通过 add_table() 写入容器。")
    result.add_table(
        [
            ["项目", "说明", "结果"],
            ["段落", "支持普通文字段落", "OK"],
            ["图片", "支持图片插入", "OK"],
            ["表格", "支持二维数据渲染", "OK"],
        ]
    )
    result.add_table_caption_auto("基础能力示例表")

    context = {
        "text_tag": make_rich_text("Demo4：容器中表格 + 表题注。", BODY_STYLE),
        "image_tag": api.new_container().subdoc,
        "table_tag": api.new_container().subdoc,
        "result": result.subdoc,
    }
    api.render(context, str(OUTPUT_PATH))
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Generated: {main()}")
