"""演示表格单元格内文字与图片混排。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from docxspec import WordAPI, make_table_style


def build_demo_image(image_path: Path) -> None:
    """生成一张用于测试方法步骤中的示例拓扑图。"""

    image_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (720, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 85, 180, 175), outline="#1F4E79", width=4)
    draw.rectangle((285, 85, 435, 175), outline="#70AD47", width=4)
    draw.rectangle((540, 85, 690, 175), outline="#C00000", width=4)
    draw.text((80, 120), "Input", fill="#1F4E79")
    draw.text((325, 120), "Memory", fill="#70AD47")
    draw.text((585, 120), "Output", fill="#C00000")
    draw.line((180, 130, 285, 130), fill="#222222", width=4)
    draw.line((435, 130, 540, 130), fill="#222222", width=4)
    draw.polygon([(285, 130), (265, 120), (265, 140)], fill="#222222")
    draw.polygon([(540, 130), (520, 120), (520, 140)], fill="#222222")
    image.save(image_path)


def main() -> None:
    template_path = ROOT_DIR / "Demo" / "template.docx"
    output_dir = ROOT_DIR / "Demo" / "output"
    image_path = output_dir / "mixed_cell_test_method.png"
    output_path = output_dir / "demo11_table_mixed_cell.docx"

    build_demo_image(image_path)

    api = WordAPI(str(template_path))
    container = api.new_container()
    container.add_heading("表格单元格混排示例", level=1)
    container.add_table(
        [
            ["字段", "内容"],
            ["测试项标识", "FT_Memory_YJCS_001"],
            [
                "测试方法",
                [
                    "1. 搭建测试模型拓扑\n",
                    {"image": str(image_path), "width_cm": 6.0},
                    "\n2. 配置 Memory 元件初始条件参数：0\n",
                    "3. 运行仿真并记录输出数据",
                ],
            ],
            ["判定准则", "输出数据与预期结果一致。"],
        ],
        table_style=make_table_style(col_widths_cm=[3.0, 12.0]),
    )

    api.render({"result": container.subdoc}, str(output_path))
    print(output_path)


if __name__ == "__main__":
    main()
