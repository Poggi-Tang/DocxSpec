# Contributing

Thanks for contributing to `easy-doc`.

## Development setup

```bash
git clone https://github.com/Poggi-Tang/easydocx.git
cd easydocx
pip install -e .[dev]
```

## Local checks

```bash
ruff check .
pytest
python -m build
```

## Commit convention

This repository uses **Conventional Commits** so release automation can determine semantic versions.

Examples:

- `feat: add table caption helper`
- `fix: preserve paragraph alignment when replacing placeholders`
- `docs: refresh README examples`
- `chore: update CI matrix`

Breaking changes should use `!` or a `BREAKING CHANGE:` footer.

## Pull requests

- Keep changes focused.
- Add or update tests when behavior changes.
- Update documentation if API usage changes.
