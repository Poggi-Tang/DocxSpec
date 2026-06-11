# Changelog

All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog*, and this project adheres to *Semantic Versioning*.

---

## [0.0.9] - 2026-06-11

### Added

* Added mixed table cell content support:
  * text and images can be inserted into the same table cell in order
  * image parts support `width_cm` and `height_cm`
  * both compact `{"image": "..."}` and explicit `{"type": "mixed", "parts": [...]}` schemas are supported
* Added a demo for inserting a controlled-size image into a test-method table cell.

### Changed

* `insert_table_by_config()` now preserves structured cell values instead of converting every cell to text before rendering.

---

## [0.0.8] - 2026-06-11

### Added

* Added Word field refresh helpers:
  * mark generated documents to refresh fields when opened
  * normalize table list fields to the standard `TOC \h \z \c "表"` form
  * optionally refresh fields immediately through Microsoft Word COM on Windows
* Added tests for field refresh metadata and table list field normalization.

### Changed

* Extended KL standardization support for heading spacing and standard caption fields.

---

## [0.0.3] - 2026-04-22

### Added

* Initial public release
* Core API: `WordAPI` and container-based content construction
* Support for:

  * text insertion
  * image insertion
  * table insertion
* Automatic figure and table caption numbering
* Page field support (`PAGE`, `NUMPAGES`)
* Rich text utilities
* Demo examples (`Demo/`)
* Test suite (`pytest`)
* CI workflow (GitHub Actions)
* PyPI publishing via Trusted Publishing

### Notes

* First version intended for public use

---

## [0.0.2]

### Internal

* Prototype version (not published)

---

## [0.0.1]

### Internal

* Initial project setup
