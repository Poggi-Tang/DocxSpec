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
