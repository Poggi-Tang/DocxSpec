from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import BODY_STYLE, WordAPI, make_rich_text

TEMPLATE_PATH = ROOT / "tests" / "templates" / "template.docx"
IMAGE_PATH = ROOT / "tests" / "templates" / "docxspec.png"
OUTPUT_PATH = ROOT / "output" / "tutorial_report.docx"


def build_report() -> Path:
    """Generate a small teaching report that demonstrates the main API."""
    api = WordAPI(str(TEMPLATE_PATH))

    title_text = make_rich_text("docxspec tutorial report", BODY_STYLE)

    image_container = api.new_container()
    image_container.add_heading("1. Insert an image", level=1)
    image_container.add_paragraph(
        "Use `new_container()` to prepare a sub-document, then call "
        "`add_image()` to place an image into the template."
    )
    image_container.add_image(str(IMAGE_PATH), width_cm=8.0, align="center")
    image_container.add_figure_caption_auto("Project logo example")

    table_container = api.new_container()
    table_container.add_heading("2. Insert a table", level=1)
    table_container.add_paragraph(
        "Tables can be inserted directly from nested lists, or configured "
        "through `add_table_by_config()` when more control is needed."
    )
    table_container.add_table(
        [
            ["Item", "Description", "Status"],
            ["Template rendering", "Fill placeholders in a .docx template", "OK"],
            ["Image blocks", "Insert images with width or height control", "OK"],
            ["Table blocks", "Render structured rows and columns", "OK"],
        ]
    )
    table_container.add_table_caption_auto("Core capability overview")

    result_container = api.new_container()
    result_container.add_heading("3. Mixed content", level=1)
    result_container.add_paragraph(
        "The same report can combine headings, paragraphs, figures, tables, "
        "captions, and page breaks."
    )
    result_container.add_paragraph(
        "After `render()`, you can continue processing the generated file, "
        "for example by writing a header and footer."
    )

    context = {
        "text_tag": title_text,
        "image_tag": image_container.subdoc,
        "table_tag": table_container.subdoc,
        "result": result_container.subdoc,
    }

    api.render(context, str(OUTPUT_PATH))
    api.write_header_footer(str(OUTPUT_PATH), header_text="docxspec tutorial")
    return OUTPUT_PATH


if __name__ == "__main__":
    output_file = build_report()
    print(f"Tutorial report generated: {output_file}")
