# Changelog

All notable changes to this project will be documented in this file.

The format is based on *Keep a Changelog*, and this project adheres to *Semantic Versioning*.

---

## [0.1.2] - 2026-11-25

### Fixed

* Write DOCX settings, table properties, and style metadata in schema order.
  Link the settings part when a document lacks one.
* Check Word field and directory results across document stories before saving.
* Stop cancelled Studio preview processes so queued previews can run.
* Keep stale preview feedback visible while scrolling, clarify the engine
  switch action, and fit PDFs to the available width on narrow screens.

## [0.1.1] - 2026-11-20

### Fixed

* Restore the core-properties namespace after loading document composition so
  writing the last modifier updates the existing DOCX metadata field.
* Confirm an identical retry of an already saved Studio revision when the
  original response was lost. Preserve divergent drafts and explain how to
  copy them when the server has a newer revision.

## [0.1.0] - 2026-11-20

### Added

* Studio V2 adds a component library, template sets with version history, and
  Office-backed PDF preview. AI-assisted conversion creates an editable template
  for review with the built-in DS styles.
* Studio V2 exports portable template bundles with their referenced images.
* `docxspec[report]` exposes the shared template model and a Python API to render
  those bundles to DOCX using supplied data.
* Report bundles record the DS master fingerprint so an incompatible master is
  reported before rendering.

### Changed

* Studio and Python use the same compiler for repeat blocks, conditions, captions,
  DS styles, and page settings. Python report generation can run without Studio or
  an installed Office engine.

### 2026-11-16 — DS 内置母版与 Studio 章节结构

#### 新增

* WordAPI、标准文档生成和 Studio 输出携带完整的 17 个 DS 样式，未使用的样式也保留，
  方便接收方在 Word/WPS 中人工编辑。新增 `ensure_ds_styles()`，复制缺失样式及编号依赖，
  重映射冲突 ID，并保留自定义模板已有的同名样式。样式包含字体引用，不嵌入字体文件。
* Studio 从内置 DOCX 读取默认结构：封面、修改记录、目录、图目录、表目录，以及当前
  母版中的两组 1—6 级标题。用例区位于第一组六级标题下，保存和 JSON 导入导出保留层级。
  旧模板仍可按原结构打开，新母版草稿使用独立 localStorage 键，原草稿不被覆盖。
* Studio 新增 `--refresh-fields`：在 Windows 上通过 Microsoft Word COM 更新域，
  重建目录后再次分页、刷新各 StoryRange 和目录页码，再保存文档。
  使用前安装 `pip install -e ".[word]"`；Word 不可用或刷新失败时导出报错。

#### 调整

* 内置母版使用 DS 样式。字体、标题编号、表格、图片、题注、目录及各节页眉页脚
  沿用选定母版，规范检查保持旧文档兼容性。
* Studio 默认直接继承母版排版，仅为用户明确修改的属性写入直接格式，避免字号、
  行距和字体默认值覆盖母版。正文按实际标题级别导出，前置页保留在原有位置。
* 域专项文档生成器也携带完整 DS 样式，但故意保留 `999` 和 `STALE TOC` 供手工验证。
* 浏览器验证默认使用 Playwright 安装的 Chromium；支持 `STUDIO_BROWSER_PATH` 和
  `STUDIO_URL`，不再依赖 Linux 专用的 `/usr/bin/chromium` 路径。

#### 修复

* 显式关闭 Studio SQLite 连接，解决 Windows 下连接未释放导致的文件占用问题。
* 普通导出复制未使用的样式和编号依赖，并覆盖自定义模板样式 ID 冲突、重复渲染等场景。

#### 验证与边界

* Windows / Python 3.11：仓库 pytest 89 项、Studio unittest 8 项通过；
  三个真实 Playwright 浏览器流程通过；11 个 Demo 成功运行；wheel 和 sdist 构建通过。
  新增核心模块的定向 Ruff 检查通过，全量检查仍有旧类型注解及格式告警，未做无关批量改写。
* 默认启动仍只设置 `updateFields`，不等于已经刷新域。`--refresh-fields` 的调用顺序和
  失败处理已测试，本轮未重新执行真实 Word/WPS 的打开、刷新、另存和 PDF 验收。
  自动刷新是否可靠不能仅凭更新标记或单元测试判断。
* 本机数据库、测试数据、生成的 DOCX/PDF、截图和用户手工修正版不属于本次更新内容。

---

## [0.0.10] - 2026-07-16

### Fixed

* Added explicit figure/table caption sequence resets for custom chapter heading styles.
* KL standardization now emits `SEQ ... \r 1` for the first figure or table in each
  chapter, preventing numbering such as `2-4` after chapter `1-3`.

### Added

* Added `reset_sequence` to `add_figure_caption_auto()` and
  `add_table_caption_auto()`.

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
