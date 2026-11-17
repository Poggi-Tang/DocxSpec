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

先新建模板集，再新建模板。从组件库拖入画布/结构树，或点击组件卡片添加。选择容器会插入其内部，选择普通组件会插入其后。没有选择则追加到文档末尾。使用结构树选择对象、属性栏修改、箭头调整顺序。支持保存为新组件、模板复制/归档、版本恢复、撤销和本机草稿恢复。保存会创建不可变历史版本；冲突返回错误，不覆盖其他窗口的新版本。

## 排版与交付边界

- **LibreOffice**：安装 LibreOffice 并让 `soffice` 可通过 PATH 找到，或设置 `STUDIO_SOFFICE` 为可执行文件。此版本完成 Linux 实际排版及浏览器预览测试。PDF 是真实 LibreOffice 输出，**不代表 Word/WPS 的排版**；下载 DOCX 的域缓存不保证被 LibreOffice 回写。
- **Microsoft Word**：Windows 上安装桌面 Word，再安装 `pip install -e '.[studio,word]'`。适配器通过独立 COM 进程更新正文、故事范围、文本框、目录并导出 PDF，限制三次更新以检测稳定性。**当前 Linux 环境不能实测该适配器，不能据此声称 Word 验收通过。**
- **WPS**：当前未接入经过验证的自动化适配器，界面明确标记不可用。可下载 DOCX 后在 WPS 手工实测。
- 不可用的引擎不会被自动替换。切换引擎会清除旧预览；修改模板或数据会把预览标记为过期并禁用当前 DOCX 下载。
- 每次任务产生独立的 `report.docx`、`report.pdf` 和 `manifest.json`，记录引擎版本、DS 母版哈希、输入哈希及产物哈希。
- PDF 中只有能唯一匹配的文本提供点击选择；表格、图片、重复文字通过结构树选择，不伪造坐标。
- 字体必须在排版机器安装；尚无字体完整性自动认证。跨引擎、跨字体环境不能承诺像素一致。

## 组件与数据

支持标题 1–6 级、正文、矩形表格、表格/图片题注、图片、重复区块、条件区块、分页、分节和目录；页眉页脚、页码、纸张尺寸和页边距可编辑。文字默认继承 DS 母版；局部覆盖可恢复默认。表格支持行列增删、列宽、重复行和重复表头，不支持任意合并单元格、浮动对象或自由坐标布局。

文本占位为 `{{project.name}}`，可从属性栏选择数据字段。重复区块绑定数组，例如 `testCases`，内部用 `{{item.name}}`。表格重复行使用 `rows_source`，表头之后的行使用 `{{row.name}}`。条件区块使用字段与文本值相等判断，布尔值用 `true`/`false`。题注绑定同一重复范围内的表格/图片，编号由实际展开对象产生。缺失数据、孤立题注、越界列宽会明确报错。

组件保存为新的独立定义，插入的是快照，后续修改不会静默影响已有模板。图片资源不随组件保存；实例需要重新上传/绑定图片。旧版模板不会自动迁移，也不会修改旧版数据库。

## AI 转化模板

启动前配置 OpenAI-compatible 服务：

```bash
export STUDIO_AI_BASE_URL=https://your-provider.example/v1
export STUDIO_AI_MODEL=your-model
export STUDIO_AI_API_KEY=your-key
python -m studio.v2.app
```

界面会展示目标服务和发送范围。选择 DOCX 后，仅发送提取的正文和表格文本，不发送原文件、图片或宏。AI 返回固定文字、字段、重复区块、示例数据及来源映射；服务端校验模型并重置源样式和页面格式为 DS 默认。未覆盖的源内容追加到草稿末尾等待审核，图片/绘图提示手工替换。源文档内容当作数据，不作为指令。

没有模型配置时不会伪造 AI 转换。已用本机模拟服务测试协议、校验、样式清除与遗漏补全；尚未用真实外部模型验收语义准确率。当前转换审核是候选列表和源内容查看，点击定位后在属性栏编辑，尚不支持逐项接受/拒绝、复杂源文档全保真导入。

## 验证

```bash
python -m pip install pytest httpx
python -m pytest tests studio/v2/tests -q
npm --prefix studio/v2/web run build
# 安装 LibreOffice 后可额外运行真实排版测试
STUDIO_TEST_OFFICE=1 python -m pytest studio/v2/tests -q
```

浏览器实测使用本机 Chromium + Playwright，并真实调用 LibreOffice，检查新增/拖入/编辑/保存组件、重新打开模板、真实 PDF、产物 SHA256、修改后过期状态及未配置 AI 的禁用入口。截图和实测记录见 `design-qa.md`。Windows Word、WPS、外部 AI 的验收需要相应环境，不能用 Linux 结果替代。
