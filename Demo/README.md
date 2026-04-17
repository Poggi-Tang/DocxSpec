# Demo

这个目录只使用一个公共模板：

- 模板文件：`Demo/template.docx`

模板中需要包含以下 4 个标签：

```text
1 文字标签示例
{{ text_tag }}

2 图片标签示例
{{p image_tag }}

3 表格标签示例
{{p table_tag }}

4 容器标签示例
{{p result }}
```

其中 `text_tag` 按段落使用，示例脚本统一使用 `BODY_STYLE`，也就是模板里的 `KL正文`。

## 示例脚本

- `demo1_paragraph.py`
  演示直接渲染文字标签。
- `demo2_container_paragraph.py`
  演示在容器中连续添加段落。
- `demo3_container_image_caption.py`
  演示在容器中添加图片和图题注。
- `demo4_container_table_caption.py`
  演示在容器中添加表格和表题注。
- `demo5_container_table_image_caption.py`
  演示在容器中添加带图片单元格的表格和表题注。
- `demo6_header_footer.py`
  演示渲染后统一写入页眉页脚。
- `demo7_styles_in_container.py`
  演示把公开样式尽量都走一遍，其中正文相关样式放进容器，页眉页脚样式通过 `write_header_footer()` 演示。
- `demo8_all_in_one.py`
  演示文字、图片、表格、容器、题注、分页、页眉页脚全部一起使用。

## 运行方式

在仓库根目录执行：

```bash
python Demo/demo1_paragraph.py
python Demo/demo2_container_paragraph.py
python Demo/demo3_container_image_caption.py
python Demo/demo4_container_table_caption.py
python Demo/demo5_container_table_image_caption.py
python Demo/demo6_header_footer.py
python Demo/demo7_styles_in_container.py
python Demo/demo8_all_in_one.py
```

输出文件统一写到 `Demo/output/` 目录。

## 素材说明

- 公共模板：`Demo/template.docx`
- 示例图片：`Demo/docxspec.png`

如果模板里预置了以下样式名，最终效果会更接近库的默认能力：

- `KL主标题`
- `KL一级标题`
- `KL二级标题`
- `KL三级标题`
- `KL正文`
- `KL题注`
- `KL页眉`
- `KL页脚`
- `KL图片`
- `KL表格表头`
- `KL表格文字`
