# DocxSpec Studio V2

组件化报告模板编辑器。采用方案 3 的模板树、底部组件库、右侧属性栏；文档画布使用实际排版引擎导出的 PDF，不使用 HTML 模拟 Office 分页。旧 Studio 不受影响。

## 启动

在仓库根目录执行（Python 3.11+，Node 20.19+）：

```bash
python -m pip install -e '.[studio]'
npm --prefix studio/v2/web ci
npm --prefix studio/v2/web run build
python -m studio.v2.app
```

打开 http://127.0.0.1:4177 。数据默认保存在 `studio/v2/.data/`，可用 `--data-dir /path/to/data` 指定目录。备份时停止服务并复制完整数据目录（SQLite、图片、任务产物）。此版本是本机单用户工具，只绑定 loopback 并拒绝跨站访问，不要直接暴露到公网。

先创建模板集并选择排版引擎，再在其中新建模板。引擎在创建表单里标注当前是否可用。拖拽组件时，高亮落点标明插在目标前、后或容器内部。预览中可定位的文字支持在其前后插入，其他组件可以从结构树定位。点击组件卡片会在当前选中组件后、选中容器内或文末添加组件。

使用结构树选择对象、属性栏修改、箭头调整顺序。窄屏通过“模板与结构”“画布与组件”“属性”切换，选中组件进入属性区。支持保存为新组件、模板复制/归档、版本恢复、撤销和本机草稿恢复。改动保存后会创建历史版本。保存请求期间的新编辑会保留在本机草稿中，切换模板前会一并保存。发生版本冲突时，可以用“复制模板”另存本机内容。

每个编辑会话有自己的本机草稿。当同一模板存在多份草稿，或草稿基于旧版本时，从工具栏的“本机草稿”选择一份恢复。切换模板会等待当前图片上传完成，随后保存图片关联。

## 排版与交付边界

- **LibreOffice**：安装 LibreOffice 并让 `soffice` 可通过 PATH 找到，或设置 `STUDIO_SOFFICE` 为可执行文件。此版本完成 Linux 实际排版及浏览器预览测试。PDF 是真实 LibreOffice 输出，**不代表 Word/WPS 的排版**；下载 DOCX 的域缓存不保证被 LibreOffice 回写。
- **Microsoft Word**：Windows 上安装桌面 Word，再安装 `pip install -e '.[studio,word]'`。适配器通过独立 COM 进程更新正文、故事范围、文本框、目录并导出 PDF，限制三次更新以检测稳定性。**当前 Linux 环境不能实测该适配器，不能据此声称 Word 验收通过。**
- **WPS**：当前未接入经过验证的自动化适配器，界面明确标记不可用。可下载 DOCX 后在 WPS 手工实测。
- 不可用的引擎不会被自动替换。切换引擎会清除旧预览；修改模板或数据会把预览标记为过期并禁用当前 DOCX 下载。
- 每次任务产生独立的 `report.docx`、`report.pdf` 和 `manifest.json`，记录引擎版本、DS 母版哈希、输入哈希及产物哈希。
- PDF 支持适合整页、适合宽度、缩放和跳页。下载文件名带模板名与版本，内容来自当前预览绑定的任务。
- 排版引擎设置属于正在编辑的模板所在的模板集。浏览另一个模板集时，当前模板及其引擎继续显示。
- PDF 中只有能唯一匹配的文本提供点击选择；表格、图片、重复文字通过结构树选择，不伪造坐标。
- 字体必须在排版机器安装；尚无字体完整性自动认证。跨引擎、跨字体环境不能承诺像素一致。

## 组件与数据

支持标题 1–6 级、正文、矩形表格、表格/图片题注、图片、重复区块、条件区块、分页、分节和目录；页眉页脚、页码、纸张尺寸和页边距可编辑。文字默认继承 DS 母版；局部覆盖可恢复默认。表格支持行列增删、列宽、重复行和重复表头，不支持任意合并单元格、浮动对象或自由坐标布局。

文本占位为 `{{project.name}}`，可从属性栏选择数据字段。重复区块绑定数组，例如 `testCases`，内部用 `{{item.name}}`。表格重复行使用 `rows_source`，表头之后的行使用 `{{row.name}}`。条件区块使用字段与文本值相等判断，布尔值用 `true`/`false`。题注绑定同一重复范围内的表格/图片，编号由实际展开对象产生。缺失数据、孤立题注、越界列宽会明确报错。

字段会插入光标位置或替换选中的文字。“测试数据”默认显示表单，可以修改字段、添加和删除用例记录。高级 JSON 提供完整数据编辑，格式错误显示在输入框旁。

组件保存为新的独立定义，插入的是快照，后续修改不会静默影响已有模板。图片资源不随组件保存；实例需要重新上传/绑定图片。旧版模板不会自动迁移，也不会修改旧版数据库。

## 导出模板包并用 Python 生成报告

打开模板后，点击工具栏「导出模板包」。ZIP 包含当前编辑内容和引用的固定图片，包括尚未保存的模板改动。测试数据、预览和 AI 审核记录留在 Studio。生成报告时，Python 单独读取业务数据。安装与导出端匹配的 DocxSpec 版本以保留相同的 DS 母版。

```bash
python -m pip install "docxspec[report]==0.1.1"
```

```python
import json
from pathlib import Path

from docxspec.report import render_report

data = json.loads(Path("data.json").read_text(encoding="utf-8"))
render_report("验收模板-模板包.zip", data, "验收报告.docx")
```

如果图片组件绑定到数据字段，例如 `result.screenshot`，先将本次报告的图片注册到本地资源目录，再传入图片 ID：

```python
from docxspec.report import register_report_asset, render_report

assets = Path("report-assets")
data["result"]["screenshot"] = register_report_asset("screenshot.png", assets)
render_report("验收模板-模板包.zip", data, "验收报告.docx", assets=assets)
```

Python 使用与 Studio 相同的组件和样式规则生成 DOCX。实际分页、PDF 预览和域缓存更新取决于所选排版引擎，见上方说明。

## AI 转化模板

启动前配置 OpenAI-compatible 服务：

```bash
export STUDIO_AI_BASE_URL=https://your-provider.example/v1
export STUDIO_AI_MODEL=your-model
export STUDIO_AI_API_KEY=your-key
python -m studio.v2.app
```

界面会展示目标模板集、目标服务和发送范围。选择 DOCX 后，先确认文件名并点击“开始转换”。转换仅发送提取的正文和表格文本，不发送原文件、图片或宏。AI 返回固定文字、字段、重复区块、示例数据及来源映射；服务端校验模型并重置源样式和页面格式为 DS 默认。未覆盖的源内容追加到草稿末尾等待审核，图片/绘图提示手工替换。源文档内容当作数据，不作为指令。

转换完成后可在通知中打开审核，并从生成模板的工具栏重新进入。逐项对照原文与当前模板组件，可定位编辑、切换上下项并标为已审核。审核标记记录核对进度，刷新后仍可查看。

已用本机模拟服务测试协议、校验、样式清除与遗漏补全。真实外部模型的语义准确率待验收，逐项接受/拒绝和复杂源文档保真导入仍是后续范围。

## 验证

```bash
python -m pip install pytest httpx
python -m pytest tests studio/v2/tests -q
npm --prefix studio/v2/web run build
# 安装 LibreOffice 后可额外运行真实排版测试
STUDIO_TEST_OFFICE=1 python -m pytest studio/v2/tests -q
```

浏览器实测使用本机 Chromium + Playwright，并真实调用 LibreOffice，检查新增/拖入/编辑/保存组件、重新打开模板、真实 PDF、产物 SHA256、修改后过期状态及未配置 AI 的禁用入口。截图和实测记录见 `design-qa.md`。Windows Word、WPS、外部 AI 的验收需要相应环境，不能用 Linux 结果替代。

将 Studio 指向独立测试数据目录后，可运行 `python studio/v2/tests/browser_interactions.py`，验证延迟请求、撤销、模板切换、字段范围和多页 PDF 定位。测试默认连接 4177 端口，可用 `STUDIO_TEST_URL` 更改。

同一实例可运行 `python studio/v2/tests/browser_drafts.py` 验证多标签草稿和复制期间保存，以及 `python studio/v2/tests/browser_navigation.py` 验证延迟上传、归档、历史窗口和数字条件。

`python studio/v2/tests/browser_ux.py` 覆盖首次创建、弹窗键盘操作、测试数据与窄屏编辑。`python studio/v2/tests/browser_components.py` 覆盖实际拖放、光标插入和样式校验。

`python studio/v2/tests/browser_template_bundle.py` 验证通过工具栏导出模板包，以及用独立业务数据生成 DOCX。

验证 AI 审核时，先运行 `python studio/v2/tests/browser_model_fixture.py`，再为测试用 Studio 设置 `STUDIO_AI_BASE_URL=http://127.0.0.1:4223/v1` 和 `STUDIO_AI_MODEL=browser-fixture`。启动 Studio 后用 `STUDIO_TEST_AI=1 python studio/v2/tests/browser_interactions.py` 执行完整交互回归。
