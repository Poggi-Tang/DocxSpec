# docxspec
English | [简体中文](https://github.com/Poggi-Tang/docxspec/blob/main/README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![Python](https://img.shields.io/pypi/pyversions/docxspec?cacheSeconds=300)](https://pypi.org/project/docxspec/)
[![License](https://img.shields.io/github/license/Poggi-Tang/docxspec)](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE)
[![CI](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/ci.yml)
[![Publish](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml/badge.svg)](https://github.com/Poggi-Tang/docxspec/actions/workflows/publish.yml)


`docxspec` is a lightweight Word report generation library built on top of `python-docx`.

It provides a small, structured API for generating `.docx` reports from templates and
containerized content blocks. It is suitable for automated test reports, simulation reports,
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
from docxspec import WordAPI
from docxspec import BODY_STYLE, make_rich_text

api = WordAPI("templates/test.docx")

text = make_rich_text(
    "This text is inserted into the template.",
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

## Example Script

A runnable teaching example is available at `examples/generate_tutorial_report.py`.

From the repository root:

```bash
python examples/generate_tutorial_report.py
```

The script reuses the test template and image in `tests/templates/` and writes
the generated file to `output/tutorial_report.docx`.

## Project Structure

```text
docxspec
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── publish.yml
│       └── release.yml
├── examples/
├── src/
│   └── docxspec/
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

## License

MIT License. See [LICENSE](https://github.com/Poggi-Tang/docxspec/blob/main/LICENSE).

## Contact

Scan the QR code to add me on WeChat:

![WeChat QR Code](https://github.com/Poggi-Tang/docxspec/blob/main/src/image/or_code.bmp)
