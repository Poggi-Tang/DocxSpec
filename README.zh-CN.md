# docxspec

[English](https://github.com/Poggi-Tang/DocxSpec/blob/main/README.md) | 简体中文

[![PyPI](https://img.shields.io/pypi/v/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![Python](https://img.shields.io/pypi/pyversions/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![License](https://img.shields.io/github/license/Poggi-Tang/DocxSpec)](https://github.com/Poggi-Tang/DocxSpec/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/publish.yml)

`docxspec` 是一个基于 `python-docx` 构建的 **结构化 Word 报告生成库**。

它提供了一套轻量、模板驱动的 API，用于从用户提供的 `.docx` 模板生成标准化报告，适用于自动化测试报告、仿真报告以及工程文档生成场景。

---

## 功能特性

* 基于模板的 Word 报告生成
* 结构化内容容器（Container）机制
* 支持文本、图片、表格插入
* 富文本样式辅助工具
* 图/表题注自动编号
* 页码字段支持（`PAGE` / `NUMPAGES`）
* Word 域刷新辅助能力（目录、图目录、表目录、题注）
* KL 标准文档识别、校验与组装
* 完整的 PyPI 打包与 CI/CD 流程

---

## 安装

从 PyPI 安装：

```bash id="w4v9lb"
pip install docxspec
```

或从源码安装：

```bash id="q2xw3e"
git clone https://github.com/Poggi-Tang/DocxSpec.git
cd DocxSpec
pip install -e .
```

---

## 快速开始

```python id="3x9a8p"
from docxspec import BODY_STYLE, WordAPI, make_rich_text

api = WordAPI("your_template.docx")

text = make_rich_text(
    "这是一段插入到模板中的文本内容",
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

使用自定义章节标题样式时，每个章节的第一条图/表题注应显式重置序列，避免章节号已经
变化但 Word 仍沿用上一章的题注流水号：

```python
chapter = api.new_container()
chapter.add_heading("测试记录", level=1)
chapter.add_table_caption_auto("第一张表", reset_sequence=True)
chapter.add_table([["名称", "数值"]])
chapter.add_table_caption_auto("第二张表")
chapter.add_table([["名称", "数值"]])
```

章节第一条题注会使用 `SEQ 表 \r 1`，后续题注继续递增；
`add_figure_caption_auto()` 同样支持 `reset_sequence`。

表格单元格支持文字和图片混排，图片块可以单独设置尺寸：

```python id="mixed-cell"
table_container.add_table(
    [
        ["字段", "内容"],
        [
            "测试方法",
            [
                "1. 搭建测试模型拓扑\n",
                {"image": "topology.png", "width_cm": 6.0},
                "\n2. 运行仿真并记录输出数据",
            ],
        ],
    ]
)
```

如果使用 JSON 式配置，也可以写成 `{"type": "mixed", "parts": [...]}`，
图片块可写成 `{"type": "image", "path": "...", "width_cm": 3.0}`。

---

## 工作原理

`docxspec` 的核心由两部分组成：

1. **WordAPI**

   * 负责加载模板
   * 渲染内容
   * 输出最终 Word 文档

2. **Container（容器）机制**

   * 用于构建结构化内容块
   * 支持图片、表格、题注、段落等组合内容

典型流程如下：

1. 准备 Word 模板
2. 构建文本或容器内容
3. 将内容传入 `api.render(...)`
4. 输出最终报告

---

## 模板要求

`docxspec` 是一个 **模板驱动型库**。

使用时需要注意：

* 模板结构需与 `render` 中的占位逻辑一致
* 模板中需预先定义所需的段落/表格样式
* 若项目依赖特定样式（如报告规范），需在模板中提前配置

仓库中的 `Demo/template.docx` 提供了一个可运行示例
（注意：Demo 模板不会被打包到发布的 wheel 中）

---

## Word 域刷新

`docxspec` 可以给生成后的 `.docx` 写入打开自动刷新标记，使 Word/WPS 在打开文档时刷新目录、图目录、表目录和题注等域。若运行环境为 Windows，且已安装 Microsoft Word 和 `pywin32`，也可以通过 Word COM 立即刷新域。

```python id="field-refresh"
from docxspec import refresh_docx_fields

result = refresh_docx_fields("report.docx", use_word=True)
print(result.word_refreshed, result.error)
```

需要立即调用 Word COM 刷新时安装可选依赖：

```bash id="install-word-extra"
pip install "docxspec[word]"
```

未安装 Microsoft Word 或 `pywin32` 时，`refresh_docx_fields()` 仍会写入 `updateFields` 标记，文档打开后可由 Word/WPS 刷新域。

---

## 示例目录

仓库中提供了完整示例，位于 `Demo/` 目录：

公共模板：

* `Demo/template.docx`

示例脚本：

* `Demo/demo1_paragraph.py`
* `Demo/demo2_container_paragraph.py`
* `Demo/demo3_container_image_caption.py`
* `Demo/demo4_container_table_caption.py`
* `Demo/demo5_container_table_image_caption.py`
* `Demo/demo6_header_footer.py`
* `Demo/demo7_styles_in_container.py`
* `Demo/demo8_all_in_one.py`
* `Demo/demo9_block_template.py`
* `Demo/demo10_kl_standard.py`
* `Demo/demo11_table_mixed_cell.py`

运行示例：

```bash id="9g2l1s"
python Demo/demo1_paragraph.py
python Demo/demo8_all_in_one.py
```

生成文件默认输出到 `Demo/output/` 目录。

---

## 项目结构

```text id="b7n3kx"
DocxSpec
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

---

## 发布流程

本项目采用标准 Python 包工程流程：

* GitHub Actions 自动执行 CI（测试 / 校验）
* 使用 Trusted Publishing 发布到 PyPI
* 同时构建 sdist 和 wheel 包

---

## 开发

```bash id="x9m3pl"
pip install -e .[dev]
pytest
ruff check .
```

开发时建议自行准备 `.docx` 模板文件，并通过路径传入 `WordAPI`。

---

## 许可证

MIT License，详见 [LICENSE](https://github.com/Poggi-Tang/DocxSpec/blob/main/LICENSE)。
