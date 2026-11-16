# DocxSpec Studio 验收记录

完成日期：2026-11-16（Asia/Shanghai）。

**结论：当前本地编辑、模板保存和报告生成范围有条件通过。WPS 打开时自动刷新全部域未通过，不支持把本版本认定为无人值守域刷新方案。**

## 实测环境

- Linux Debian 13，Chromium + Playwright。
- WPS Writer 11.1.0.11723.XA，官方国际站分发的 Linux 安装包，真实 GUI 操作。
- LibreOffice 25.2.3.2，补充交叉渲染检查。
- 未运行 Microsoft Word，也未覆盖其他 WPS 版本。

## 验收结果

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 编辑、保存、刷新恢复、模板库重开、JSON 导入导出 | 通过 | `verify_workflow.py` |
| 未失焦文字刷新后恢复、章节正文、撤销重做 | 修复后通过 | `verify_acceptance.py` |
| 100 条用例生成，101 条拒绝 | 通过 | `evidence/acceptance/100-cases.docx` |
| 数据筛选、重复、空数据、图片、DS 样式及非法输入 | 通过 | 4 项后端测试、浏览器回归 |
| WPS 打开生成的报告 | 通过 | `evidence/acceptance/wps-reopened.png` |
| WPS 另存 DOCX、重新打开 | 通过 | `wps-saved-report.docx`；另存前后全部段落/表格文字一致，图片数量及 DS 样式保留 |
| WPS 导出 PDF | 通过，6 页 A4 | `wps-report.pdf`、`wps-page-3.png`、`wps-page-4.png` |
| 短表格分页 | 本样例通过 | 第二用例标题、全部行和截图占位同在第 4 页 |
| 仅打开时自动更新目录、SEQ 和 REF 域 | **未通过** | `wps-fields-before.png`，仍显示 STALE TOC / 999 |
| 正文中 Ctrl+A、F9 更新 TOC、SEQ、REF | 通过 | `wps-fields-after.png`、`wps-fields-updated.docx` |
| 页码渲染 | WPS PDF 中通过 | `wps-fields-updated.pdf` 显示 Page 1 of 2、Page 2 of 2 |
| 页脚域缓存完全刷新 | **未通过** | 仅更新正文后另存的 footer XML 缓存仍为 999；PDF 中动态计算正确不代表缓存已刷新 |

以上相对文件名除测试脚本外均在 `evidence/acceptance/`。

## 验收中修复的问题

编辑器此前仅在文字失焦时更新模型，直接刷新会丢失最后一段输入。现改为输入时立即更新模型与本地草稿，同一次编辑只记录一个撤销步骤。名称、步骤、实际结果、章节说明和章节正文均已回归验证。

## WPS 弹窗及环境处理

- 首次启动许可协议：已确认；重新打开不再阻塞。
- 默认模板加载失败：用户目录只读，将 WPS 数据目录映射到工作区后解决。
- PDF 导出失败：补齐 `libtiff.so.5` / `libwebp.so.6` 后成功导出。
- Symbol/Wingdings 等字体提示：已记录并关闭；验收报告使用 Noto Serif CJK SC，不包含依赖这些字体的公式。公式/特殊符号兼容性不在通过范围内。
- WPS PDF 经 Poppler 检查时提示嵌入字体类型不匹配，但本样例文本提取及页面渲染正常；未进行 PDF/A 等格式认证。

已逐个检查并处理阻塞窗口；未用关闭弹窗代替文档验收。最终 WPS 窗口证据为 `wps-report-open.png`，无阻塞弹窗。

## 使用限制与域更新建议

当前模板格式是 Studio JSON；任意 DOCX 无损导入还原仍未实现。浏览器画布不提供 Word 精确分页，长表格仍可能自然跨页。

`updateFields=true` 只是打开更新请求，不能当作刷新完成。本次使用额外的受控 `field-probe.docx` 专门验证域行为，Studio 的常规测试报告本身不生成目录/题注域。若使用含域模板，需在目标 Office 中更新正文，并单独检查页眉页脚和文本框中的域，再保存并核对最终 PDF。不能仅靠正文 Ctrl+A、F9 保证所有区域的缓存都更新。

正式发布若要求无人值守自动刷新或 Microsoft Word 兼容，应将这两项设为尚未满足的发布条件。
