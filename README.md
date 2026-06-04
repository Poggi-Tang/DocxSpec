# docxspec

English | [简体中文](https://github.com/Poggi-Tang/DocxSpec/blob/main/README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![Python](https://img.shields.io/pypi/pyversions/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![License](https://img.shields.io/github/license/Poggi-Tang/DocxSpec)](https://github.com/Poggi-Tang/DocxSpec/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/DocxSpec/actions/workflows/publish.yml)

`docxspec` is a structured Word report generation library built on top of `python-docx`.

It provides a small, template-driven API for generating `.docx` reports from user-supplied templates and containerized content blocks. It is designed for automated test reports, simulation reports, and other engineering document workflows.

## Features

* Template-based Word report generation
* Structured content container API
* Text, image, and table insertion
* Rich text style helpers
* Automatic figure and table caption numbering
* Page field helpers such as `PAGE` and `NUMPAGES`
* KL-standard document classification, validation, and standard document assembly
* PyPI-ready packaging and CI/CD workflows

## Installation

Install from PyPI:

```bash id="a01x9k"
pip install docxspec
```

Or install from source:

```bash id="frx0as"
git clone https://github.com/Poggi-Tang/DocxSpec.git
cd DocxSpec
pip install -e .
```

## Quick Start

```python id="24yi91"
from docxspec import BODY_STYLE, WordAPI, make_rich_text

api = WordAPI("your_template.docx")

text = make_rich_text(
    "This text is inserted into the template.",
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
            ["Name", "Value"],
            ["Example", "123"],
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

## How It Works

`docxspec` uses two main ideas:

1. `WordAPI` loads a `.docx` template and renders the final output.
2. Containers are used to build structured sub-document blocks such as images, tables, captions, and styled paragraphs.

A typical workflow is:

1. Prepare a Word template
2. Build text or container content
3. Pass the rendered blocks into `api.render(...)`
4. Export the final report

## Template Requirements

`docxspec` is template-driven.

When preparing your own template, make sure that:

* the template structure matches the placeholders or render targets used by your code
* the required paragraph / table styles exist in the template
* custom report styles are defined in advance if your project depends on them

The demo template in `Demo/template.docx` is provided as a runnable example, but demo assets are not packaged into the published wheel. The KL master template used by `build_standard_docx()` is bundled separately as package data.

## KL Standard Documents

`docxspec` also provides KL-standard document utilities for workflows that start from an
existing body-only `.docx` file and need a standardized output document.

```python
from docxspec import build_standard_docx, check_word_standard, classify_docx_body

report = classify_docx_body("body.docx")
build_result = build_standard_docx(
    "body.docx",
    "standard.docx",
    "Demo/template.docx",
)
check_result = check_word_standard("standard.docx")
```

These APIs reuse the KL styles and field-code rules from the master template. They are intended
for document standardization and validation, while `WordAPI` remains the primary API for
template-driven report generation.

## Demo Directory

The repository includes a runnable demo set in `Demo/`.

Shared template:

* `Demo/template.docx`

Example scripts:

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

Run them from the repository root, for example:

```bash id="zr2qj0"
python Demo/demo1_paragraph.py
python Demo/demo8_all_in_one.py
python Demo/demo9_block_template.py
python Demo/demo10_kl_standard.py
```

Generated files are written to `Demo/output/`.

## Reusing Word Blocks

`BlockTemplate` can extract a repeated `caption + table` block from an existing Word
template and insert cloned copies back into a document or a container. This is useful
when the template already contains field captions, merged cells, images, or carefully
prepared table styles.

Place a marker paragraph immediately before the source caption and table:

```text
{{SOURCE_TABLE_BLOCK}}
Table <SEQ field> {{TABLE_TITLE}}
<table with placeholders>
```

Then extract and reuse the block:

```python
from docxspec import WordAPI

api = WordAPI("template.docx")
block_template = api.extract_table_block("{{SOURCE_TABLE_BLOCK}}", remove_block=True)

container = api.new_container()
container.add_block(
    block_template.clone().replace_text(
        {
            "{{TABLE_TITLE}}": "Default icon display",
            "{{ITEM_ID}}": "FT_Demo_UI_001",
        }
    )
)

api.render({"result": container.subdoc}, "report.docx")
```

For documents that must preserve Word field captions as strictly as possible, prefer
`insert_block_at_marker(...)` followed by saving the document directly.

## Project Structure

```text id="8r4z09"
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

## Release Automation

This repository is prepared for a professional Python package workflow:

* CI runs lint and tests on push and pull request
* Trusted Publishing publishes to PyPI from GitHub Actions
* Build artifacts include both source distribution and wheel

## Development

```bash id="jlwm2z"
pip install -e .[dev]
pytest
ruff check .
```

When developing locally, prepare your own `.docx` template files in the repository or project workspace and pass their paths explicitly to `WordAPI`.

## License

MIT License. See [LICENSE](https://github.com/Poggi-Tang/DocxSpec/blob/main/LICENSE).
