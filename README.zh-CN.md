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
* DS 标准文档识别、校验与组装
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

## 浏览器编辑器 Studio

[Studio V2](studio/v2/README.md) 与 Python 共用报告编译器。先在 Studio
点击「导出模板包」，导出当前组件模板及引用的固定图片。业务数据由 Python 单独传入。

```bash
python -m pip install "docxspec[report]"
```

```python
import json
from pathlib import Path

from docxspec.report import render_report

data = json.loads(Path("data.json").read_text(encoding="utf-8"))
render_report("模板.zip", data, "验收报告.docx")
```

Python 生成 DOCX 时沿用 Studio 的内容、编号、DS 样式和页面设置，可以脱离 Studio
和 Office 运行。实际排版、PDF 预览及 AI 转换可以按需在 Studio 使用。

Studio V1 可直接启动，无需 Node.js：

```powershell
python -m pip install -e .
python studio/server.py --data-dir .local-acceptance-data
```

打开 `http://127.0.0.1:4175`。网页默认从内置母版读取封面、修改记录、目录、图目录、
表目录及正文 1—6 级标题结构；当前母版含两组示例标题，用例区位于第一组六级标题下。
导出沿用母版的字体、编号、表格、图片、题注和各节页眉页脚。端口被占用时使用 `--port`。

### DS 分块母版

`build_standard_docx("正文.docx", "报告.docx")` 默认使用内置 `body.docx` 的 DS 基础样式。
每次导出都装配封面（`cover.docx`）、修订记录（`revision.docx`）和正文目录（`contents.docx`）。
正文写完后，根据实际题注域决定是否装配图录（`figures.docx`）和表录（`tables.docx`）。

要单独修改某一块，可从 `docxspec.DEFAULT_DS_SECTIONS` 复制对应文件到自己的目录，
然后传入 `front_matter_dir="my_layout"`。每个文件包含一个 Word 分节，可跨多页。编辑图录和
表录时请保留原生目录域。其余块仍取自内置文件，各块引用的同名 DS 样式统一使用基础文档的定义。

已有整份母版仍可通过 `template_docx=` 使用。`WordAPI.render()` 会在最终生成时移除整份母版
中的独立空图录和表录。自行保存 DOCX 的渲染器可在写完内容后调用
`docxspec.prune_empty_caption_lists(path)`。

Windows 上可安装 `python -m pip install -e ".[word]"`，启动时增加 `--refresh-fields`，
在下载前调用本机 Microsoft Word 更新域并保存；失败时导出报错。默认启动只写入打开更新
标记，不保证 Office 自动刷新所有区域。当前版本的真实 Word/WPS 排版与 PDF 仍需人工验收。
详见 [Studio 使用说明](studio/README.md) 和 [更新说明](CHANGELOG.md)。

---

## 模板要求

`docxspec` 是一个 **模板驱动型库**。

使用时需要注意：

* 模板结构需与 `render` 中的占位逻辑一致
* 模板中需预先定义所需的段落/表格样式
* 若项目依赖特定样式（如报告规范），需在模板中提前配置

默认输出会携带母版完整的 17 个 DS 样式，包括未使用的标题级别，方便人工续编。
自定义模板已有的同名样式保留，缺失样式及编号依赖自动补齐；字体文件本身不嵌入 DOCX。
`kl_standard` 模块名保持兼容，规范检查仍可识别旧 KL 样式。

仓库中的 `Demo/template.docx` 提供了一个可运行示例
（注意：Demo 模板不会被打包到发布的 wheel 中）

---

## Word 域刷新

`docxspec` 可以给生成后的 `.docx` 写入打开时更新域的请求标记；该标记不保证 Word/WPS 已刷新目录、图目录、表目录、题注或页脚缓存。若运行环境为 Windows，且已安装 Microsoft Word 和 `pywin32`，也可以通过 Word COM 立即刷新域。

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

域刷新结果的 `status` 为 `marked_for_update`、`refreshed` 或 `failed`。仅设置打开更新标记不表示已刷新。Word 更新失败会记录错误；`raise_on_word_error=True` 会抛出异常。当前 COM 调用尚无硬超时保证，不建议直接用于无人值守批量任务。

## 可视化测试报告编辑器

`studio/` 提供本机可运行的模板编辑器，支持磁盘保存、重新打开、配置导入导出及通过 DocxSpec 生成真实 DOCX。安装本仓库后运行 `python studio/server.py`，访问 `http://127.0.0.1:4175`。详细使用方法和当前边界见 [Studio 使用说明](studio/README.md)。
