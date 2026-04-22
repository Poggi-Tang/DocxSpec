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

The demo template in `Demo/template.docx` is provided as a runnable example, but demo assets are not packaged into the published wheel.

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

Run them from the repository root, for example:

```bash id="zr2qj0"
python Demo/demo1_paragraph.py
python Demo/demo8_all_in_one.py
```

Generated files are written to `Demo/output/`.

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
