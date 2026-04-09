from __future__ import annotations

from pathlib import Path

from easy_docx import WordAPI
from easy_docx.word_styles import BODY_STYLE, make_rich_text


def test_demo_render(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    template = project_root / "src" / "easy_docx" / "templates" / "default_template.docx"
    image = project_root / "tests" / "assets" / "test_image.png"

    api = WordAPI(str(template))
    image_container = api.new_container()
    image_container.add_image(str(image), width_cm=6.0)

    output = tmp_path / "smoke.docx"
    api.render(
        {
            "text_tag": make_rich_text("smoke", BODY_STYLE),
            "image_tag": image_container.subdoc,
            "table_tag": api.new_container().subdoc,
            "result": api.new_container().subdoc,
        },
        str(output),
    )
    assert output.exists()
