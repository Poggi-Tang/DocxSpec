# docxspec
English | [简体中文](README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![Python](https://img.shields.io/pypi/pyversions/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![License](https://img.shields.io/github/license/Poggi-Tang/docxspec)](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml)

`docxspec` is a lightweight Word report generation library built on top of `python-docx`.

It provides a small, structured API for generating `.docx` reports from user-supplied templates
and containerized content blocks. It is suitable for automated test reports, simulation reports,
and other document-generation workflows.

## Features

- Template-based Word report generation
- Structured content container API
- Text, image, and table insertion
- Rich text style helpers
- Automatic figure and table caption numbering
- PyPI-ready packaging and CI/CD workflows

## Installation

Install from PyPI:

```bash
pip install docxspec
```

Or install from source:

```bash
git clone https://github.com/Poggi-Tang/docxspec.git
cd docxspec
pip install -e .
```

## Quick Start

```python
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

## Demo Directory

The repository includes a runnable demo set in `Demo/`.

It uses one shared template file:

- `Demo/template.docx`

And provides these example scripts:

- `Demo/demo1_paragraph.py`
- `Demo/demo2_container_paragraph.py`
- `Demo/demo3_container_image_caption.py`
- `Demo/demo4_container_table_caption.py`
- `Demo/demo5_container_table_image_caption.py`
- `Demo/demo6_header_footer.py`
- `Demo/demo7_styles_in_container.py`
- `Demo/demo8_all_in_one.py`

Run them from the repository root, for example:

```bash
python Demo/demo1_paragraph.py
python Demo/demo8_all_in_one.py
```

Generated files are written to `Demo/output/`.

Note: template and demo assets are repository examples. They are not packaged into the published wheel.

## Project Structure

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

## Release Automation

This repository is prepared for a professional Python package workflow:

- **CI** runs lint and tests on push and pull request.
- **Semantic Release** updates the version, changelog, tag, and GitHub Release.
- **Trusted Publishing** publishes to PyPI from GitHub Actions without a PyPI API token.
- **Build artifacts** include both source distribution and wheel.

## Development

```bash
pip install -e .[dev]
pytest
ruff check .
```

When developing locally, prepare your own `.docx` template files in the repository or project workspace and pass their paths explicitly to `WordAPI`.

## License

MIT License. See [LICENSE](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE).
