# easy-docx

[English](README.md) | 简体中文

[![PyPI](https://img.shields.io/pypi/v/easy_uiauto?cacheSeconds=300)](https://pypi.org/project/easy-docx/)
[![Python](https://img.shields.io/pypi/pyversions/easy-docx?cacheSeconds=300)](https://pypi.org/project/easy-docx/)
[![License](https://img.shields.io/github/license/Poggi-Tang/easydocx)](https://github.com/Poggi-Tang/easydocx/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/easydocx/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/easydocx/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/easydocx/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/easydocx/actions/workflows/publish.yml)


`easy-docx` 是一个基于 `python-docx` 的轻量级 Word 报告生成库。

它提供了一套小而清晰的 API，用于基于模板和结构化内容块生成 `.docx` 文档，适用于自动化测试报告、仿真报告以及其他文档生成场景。

## 功能特点

- 基于模板的 Word 报告生成
- 结构化内容容器 API
- 支持文本、图片、表格插入
- 富文本样式辅助工具
- 支持图表标题自动编号
- 适合发布到 PyPI 的完整工程化配置

## 安装

从 PyPI 安装：

```bash
pip install easy-docx
```

或从源码安装：

```bash
git clone https://github.com/Poggi-Tang/easydocx.git
cd easydocx
pip install -e .
```

## 快速示例

```python
from easy_docx import WordAPI
from easy_docx import BODY_STYLE, make_rich_text

api = WordAPI("templates/test.docx")

text = make_rich_text(
    "这是一段插入到模板中的文字。",
    BODY_STYLE,
)

image_container = api.new_container()
image_container.add_image(
    "templates/test_image.png",
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

## 项目结构

```text
easydocx
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── publish.yml
│       └── release.yml
├── examples/
├── src/
│   └── easy_docx/
│       ├── __init__.py
│       ├── word_api.py
│       ├── word_styles.py
│       └── templates/
├── tests/
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README_CN.md
└── pyproject.toml
```

## 发布自动化

当前仓库已经按照较完整的 Python 开源库流程整理：

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

## 许可证

MIT License，详见 [LICENSE](https://github.com/Poggi-Tang/easydocx/blob/main/LICENSE)。

## 联系方式

扫描二维码添加微信：

![微信二维码](https://github.com/Poggi-Tang/easydocx/blob/main/src/image/or_code.bmp)
