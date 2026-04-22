# Contributing to DocxSpec

Thank you for your interest in contributing to DocxSpec.

This project aims to provide a structured and practical solution for Word report generation in engineering workflows. Contributions of all kinds are welcome.

---

## Ways to Contribute

You can contribute in several ways:

* Reporting bugs
* Suggesting new features
* Improving documentation
* Submitting code improvements
* Adding or improving test cases

---

## Getting Started

### 1. Fork the repository

Fork the repository on GitHub and clone it locally:

```bash id="forkclone"
git clone https://github.com/Poggi-Tang/DocxSpec.git
cd DocxSpec
```

---

### 2. Create a virtual environment

```bash id="venv"
python -m venv .venv
source .venv/bin/activate  # Linux / macOS
# or
.venv\Scripts\activate     # Windows
```

---

### 3. Install dependencies

```bash id="install"
pip install -e .[dev]
```

---

### 4. Run tests

```bash id="pytest"
pytest
```

---

## Development Guidelines

### Code Style

* Follow PEP 8
* Use meaningful variable and function names
* Keep functions focused and readable

You can run lint checks with:

```bash id="lint"
ruff check .
```

---

### Testing

* All new features should include tests
* Ensure existing tests pass before submitting a PR

---

### Commit Messages

Use clear and structured commit messages:

```text id="commitmsg"
feat: add table caption support
fix: correct footer rendering bug
refactor: simplify container API
```

Recommended prefixes:

* `feat` – new feature
* `fix` – bug fix
* `refactor` – code improvement without behavior change
* `docs` – documentation changes
* `test` – test-related changes

---

## Pull Request Process

1. Create a feature branch:

   ```bash id="branch"
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit them

3. Push to your fork:

   ```bash id="push"
   git push origin feature/your-feature-name
   ```

4. Open a Pull Request on GitHub

---

## Reporting Issues

When reporting issues, please include:

* Python version
* Library version
* Minimal reproducible example
* Expected vs actual behavior

---

## Project Scope

DocxSpec focuses on:

* Template-based Word document generation
* Structured content construction
* Engineering and report automation workflows

Out-of-scope contributions may be declined if they do not align with the project direction.

---

## Release Process (Maintainers)

Releases are triggered via Git tags:

```bash id="release"
git tag vX.Y.Z
git push origin vX.Y.Z
```

Publishing is handled automatically via GitHub Actions and Trusted Publishing.

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
