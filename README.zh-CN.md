# docxspec

[English](README.md) | 简体中文

[![PyPI](https://img.shields.io/pypi/v/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![Python](https://img.shields.io/pypi/pyversions/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![License](https://img.shields.io/github/license/Poggi-Tang/docxspec)](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml)

`docxspec` 是一个基于 `python-docx` 的轻量级 Word 报告生成库。

它提供了一套小而清晰的 API，用于基于用户自备模板和结构化内容块生成 `.docx` 文档，适用于自动化测试报告、仿真报告和其他文档生成场景。

## 功能特点

- 基于模板的 Word 报告生成
- 结构化内容容器 API
- 支持文本、图片、表格插入
- 富文本样式辅助工具
- 支持图注和表注自动编号
- 支持发布到 PyPI 的工程化配置

## 安装

从 PyPI 安装：

```bash
pip install docxspec
```

或从源码安装：

```bash
git clone https://github.com/Poggi-Tang/docxspec.git
cd docxspec
pip install -e .
```

## 快速开始

```python
from docxspec import BODY_STYLE, WordAPI, make_rich_text

api = WordAPI("your_template.docx")

text = make_rich_text(
    "这是一段插入到模板中的文字。",
    BODY_STYLE,
)

image_container = api.new_container()
image_container.add_image(
    "your_image.png",
    width_cm=8.0,
    align="center",
)

table_container = api.new_container()
table_container.add_table_by_config(
    {
        "data": [
            ["名称", "数值"],
            ["示例", "123"],
        ]
    }
)

api.render(
    {
        "text": text,
        "image": image_container.subdoc,
        "table": table_container.subdoc,
    },
    "report.docx",
)
```

## Demo 目录

仓库中提供了一套可直接运行的示例，位于 `Demo/` 目录。

这套示例统一使用一个公共模板：

- `Demo/template.docx`

包含以下示例脚本：

- `Demo/demo1_paragraph.py`
- `Demo/demo2_container_paragraph.py`
- `Demo/demo3_container_image_caption.py`
- `Demo/demo4_container_table_caption.py`
- `Demo/demo5_container_table_image_caption.py`
- `Demo/demo6_header_footer.py`
- `Demo/demo7_styles_in_container.py`
- `Demo/demo8_all_in_one.py`

在仓库根目录下可以直接运行，例如：

```bash
python Demo/demo1_paragraph.py
python Demo/demo8_all_in_one.py
```

生成结果会写入 `Demo/output/`。

注意：模板和示例资源是仓库中的演示内容，不再随发布到 PyPI 的 wheel 一起打包。

## 项目结构

```text
docxspec
├── .github/
│   └── workflows/
├── Demo/
├── src/
│   └── docxspec/
│       ├── __init__.py
│       ├── word_api.py
│       └── word_styles.py
├── tests/
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README.zh-CN.md
└── pyproject.toml
```

## 发布自动化

当前仓库已经按较完整的 Python 开源库流程整理：

- **CI**：在 push 和 pull request 时自动执行 lint 与测试。
- **Semantic Release**：自动更新版本号、CHANGELOG、Tag 和 GitHub Release。
- **Trusted Publishing**：通过 GitHub Actions 向 PyPI 发布，无需手动维护 PyPI Token。
- **构建产物**：同时生成 sdist 和 wheel。

## 本地开发

```bash
pip install -e .[dev]
pytest
ruff check .
```

本地开发时，请自行在仓库或业务项目中准备 `.docx` 模板文件，并将模板路径显式传给 `WordAPI`。

## 许可协议

MIT License，详见 [LICENSE](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE)。
