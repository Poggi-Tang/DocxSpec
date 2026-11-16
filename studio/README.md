# DocxSpec Studio

可运行的本机测试报告模板编辑器。通过 DocxSpec 生成真实 DOCX，模板和测试数据保存到 SQLite，可重新打开继续编辑。

## 启动

在仓库根目录（Python 3.11+）：

```sh
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python studio/server.py
```

Windows 将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。

浏览器访问 **http://127.0.0.1:4175**。服务仅监听本机，无需 Node.js。停止后重新启动仍可打开已保存的模板。不要使用旧原型的 `python -m http.server` 启动方式，它不提供生成与保存接口。

## 操作流程

1. 编辑章节文字、测试项名称、步骤、实际结果及结论。
2. “测试数据”中修改预期结果、增减用例、填写执行数据。用例结果设为“失败”可配合失败筛选。
3. 选中测试项，调整 DS 段落样式、字号、加粗、斜体、对齐、行距及表头底色，上传截图。
4. 点击“保存”，填写名称；已有模板可更新或另存为新模板。
5. “打开模板”从磁盘模板库读取；“导出配置”下载可迁移的 JSON，“导入配置”重新载入。
6. 点击“导出 DOCX”，下载含全部章节、表格和截图的真实报告。“生成预览”只预览当前章节内容。

DOCX 直接复用内置母版：KL 样式已重命名为 DS，1—6 级标题编号、正文、表格、图片、题注、目录、各节页眉页脚均沿用母版。第一个“封面”章节填入母版封面，保留修改记录和目录前置页；标题编号由 Word 样式提供。表格宽度按母版可用版心计算。

模板配置同时保存版式设置和测试数据快照，下一份报告可打开模板后替换测试数据、另存为新模板。DOCX 输出通过 `WordAPI.new_container()`、`insert_table()`、`render()` 生成；不是浏览器 HTML 改后缀。

## 保存及格式

- 模板数据库：默认 `studio/.data/studio.sqlite3`；可用 `--data-dir /path/to/data` 指定。备份该文件前停止服务。
- 自动草稿存于当前浏览器 localStorage；磁盘模板库必须点击“保存”。容量不足会明确提示导出配置。
- 并发修改使用版本号检测；冲突不覆盖旧内容，可另存为新模板。
- 配置版本 `docxspec-studio-v1`；兼容导入旧版 `docxspec-studio-prototype-v1`。
- 配置是 Studio 输入模型，由 `renderer.py` 转换成 DocxSpec 调用，不等同于现有库的原生任意模板协议。
- 最多 100 条用例、50 个章节，单图 5 MB / 2000 万像素，请求总计 25 MB。支持 PNG/JPEG/WebP/GIF，导出采用首帧并转成 PNG。
- 字号为 CSS 像素，生成时按 0.75 转为 Word 点数。默认复用 `src/docxspec/assets/docxspec_master_template.docx` 的宋体、字号与段落设置；未调整的区块继承母版，不额外覆盖字体。显式调整字号、行距等设置时才写入相应覆盖。

生成的 DOCX 内置完整 DS 样式库，即使未使用某个标题级别或样式，也会保留供后续人工编辑。普通 WordAPI 导出也会补齐缺失的 DS 样式及编号依赖；已有的同名样式和调用方自定义样式保留。这里携带的是字体名称与样式定义，不包含字体安装文件。

Windows 本机需要在导出时实际更新目录、题注和页眉页脚域，可安装 `python -m pip install -e ".[word]"`，然后使用 `python studio/server.py --data-dir .local-acceptance-data --refresh-fields` 启动。该选项调用 Microsoft Word 更新各 StoryRange、目录和图表目录并保存；Word 不可用或刷新失败时导出会报错，不会退回仅设置标记后声称成功。默认启动仍只设置打开更新标记，实际刷新需要 Office 执行。域专项的 `make_field_probe.py` 刻意保留 999 和 STALE TOC 缓存用于手工验证，不预先刷新。

## 当前边界

已打通编辑 → 磁盘保存 → 重新打开 → 数据填充 → 真实 DOCX 导出。

尚不支持任意 DOCX 导入还原、拖动调整表格结构、章节排序删除、多人联网协作、文档回读或 PDF 在线预览。网页默认章节从内置 DOCX 实时读取：封面、修改记录、目录、图目录、表目录，以及母版正文的两组 1—6 级标题；用例区位于第一组六级标题下。前置页预览展示母版内容，正文按真实层级导出。旧模板仍按其原结构打开，旧版浏览器草稿另存于原 localStorage 键，默认新母版草稿使用独立键；样式工具作用于测试项。

默认导出仅标记 `updateFields`；启用 `--refresh-fields` 时才调用本机 Microsoft Word 实际刷新，失败会中止导出。以往版本的 WPS 实测不会仅凭此标记自动更新全部域；正文需手动 Ctrl+A、F9，页眉页脚等区域另行检查，最终 PDF 正确不等于所有 DOCX 域缓存已刷新。浏览器画布不是 Word 排版引擎。一级章节分页，短测试表格尽量保持整块，超过单页的表格仍可能跨页。[历史验收记录](ACCEPTANCE.md) 包含旧版本 WPS 样例结果；本轮 DS 母版改动未重新完成真实 Word/WPS 打开、另存和 PDF 验收。

服务没有认证，设计为仅本机运行。业务数据保存在本机，不需要外部服务。

## 验证与开发

```sh
cd studio
../.venv/bin/python -m unittest test_studio -v
# 安装测试依赖并启动服务后：
python -m pip install playwright
python -m playwright install chromium
python verify.py
python verify_workflow.py
```

验证脚本默认使用 Playwright 安装的 Chromium；也可通过环境变量 `STUDIO_BROWSER_PATH` 指定本机浏览器可执行文件。Windows PowerShell 例如：`$env:STUDIO_BROWSER_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"`。

验证脚本会在模板库新增测试模板，建议使用独立数据目录运行服务：`python studio/server.py --data-dir /tmp/studio-test-data`。

前端构建检查：Node.js 22.12+，`npm ci && npm run build`。日常使用无需构建；Python 服务直接提供源码页面。测试证据与限制见 `design-qa.md`。

## 文件

- `master.py`：从内置 DOCX 读取网页默认章节、前置页和标题层级。
- `model.py`：模型版本、类型、大小、图片及章节层级校验。
- `renderer.py`：模型到 DocxSpec / DOCX 的编译。
- `server.py`：同源本机 HTTP 接口与 SQLite 模板存储。
- `app.js`、`index.html`：编辑交互、草稿、模板库和下载。

图标使用 Phosphor Icons（见 `icons/LICENSE`）。项目许可证遵循仓库 MIT LICENSE。
