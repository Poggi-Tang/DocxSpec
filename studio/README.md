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

模板配置同时保存版式设置和测试数据快照，下一份报告可打开模板后替换测试数据、另存为新模板。DOCX 输出通过 `WordAPI.new_container()`、`insert_table()`、`render()` 生成；不是浏览器 HTML 改后缀。

## 保存及格式

- 模板数据库：默认 `studio/.data/studio.sqlite3`；可用 `--data-dir /path/to/data` 指定。备份该文件前停止服务。
- 自动草稿存于当前浏览器 localStorage；磁盘模板库必须点击“保存”。容量不足会明确提示导出配置。
- 并发修改使用版本号检测；冲突不覆盖旧内容，可另存为新模板。
- 配置版本 `docxspec-studio-v1`；兼容导入旧版 `docxspec-studio-prototype-v1`。
- 配置是 Studio 输入模型，由 `renderer.py` 转换成 DocxSpec 调用，不等同于现有库的原生任意模板协议。
- 最多 100 条用例、50 个章节，单图 5 MB / 2000 万像素，请求总计 25 MB。支持 PNG/JPEG/WebP/GIF，导出采用首帧并转成 PNG。
- 字号为 CSS 像素，生成时按 0.75 转为 Word 点数。正文使用 Noto Serif CJK SC；本机没有该字体时 Office 会替换字体。

## 当前边界

已打通编辑 → 磁盘保存 → 重新打开 → 数据填充 → 真实 DOCX 导出。

尚不支持任意 DOCX 导入还原、拖动调整表格结构、章节排序删除、多人联网协作、文档回读或 PDF 在线预览。前五个章节为预置结构，第 3 章为测试明细；样式工具作用于测试项。

导出标记 `updateFields`，没有在后台执行 Word/WPS 域刷新。WPS 实测不会仅凭此标记自动更新全部域；正文需手动 Ctrl+A、F9，页眉页脚等区域另行检查，最终 PDF 正确不等于所有 DOCX 域缓存已刷新。浏览器画布不是 Word 排版引擎。每章分页，短测试表格尽量保持整块，超过单页的表格仍可能跨页。已完成 WPS Writer 11.1.0.11723.XA 的本样例打开、另存、重开和 PDF 导出实测；未验证 Microsoft Word，详见 [验收记录](ACCEPTANCE.md)。

服务没有认证，设计为仅本机运行。业务数据保存在本机，不需要外部服务。

## 验证与开发

```sh
cd studio
../.venv/bin/python -m unittest test_studio -v
# 安装测试依赖并启动服务后（Chromium 路径默认 /usr/bin/chromium）：
python -m pip install playwright
python verify.py
python verify_workflow.py
```

验证脚本会在模板库新增测试模板，建议使用独立数据目录运行服务：`python studio/server.py --data-dir /tmp/studio-test-data`。

前端构建检查：Node.js 22.12+，`npm ci && npm run build`。日常使用无需构建；Python 服务直接提供源码页面。测试证据与限制见 `design-qa.md`。

## 文件

- `model.py`：模型版本、类型、大小和图片校验。
- `renderer.py`：模型到 DocxSpec / DOCX 的编译。
- `server.py`：同源本机 HTTP 接口与 SQLite 模板存储。
- `app.js`、`index.html`：编辑交互、草稿、模板库和下载。

图标使用 Phosphor Icons（见 `icons/LICENSE`）。项目许可证遵循仓库 MIT LICENSE。
