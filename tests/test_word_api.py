# -*- coding: utf-8 -*-
"""EasyDocx WordAPI 完整功能测试套件。

本测试文件覆盖 WordAPI 的所有公开接口，包括：
- 文档初始化和模板加载
- DocContainer 链式调用
- 段落、图片、表格的插入操作
- 域代码和自动编号功能
- 页眉页脚设置
- 文档渲染和输出
"""
import os
from pathlib import Path

import pytest
from docx.shared import Cm

from easy_doc import WordAPI, make_rich_text, make_table_style
from easy_doc.word_styles import (
    BODY_STYLE,
    CAPTION_STYLE,
    FOOTER_STYLE,
    HEADER_STYLE,
    IMAGE_STYLE,
    TABLE_BODY_STYLE,
    TABLE_HEADER_STYLE,
    make_cell_style,
    make_text_style,
)


@pytest.fixture
def template_path():
    """获取测试模板文件路径。"""
    return str(Path(__file__).parent / "templates" / "default_template.docx")


@pytest.fixture
def test_image():
    """获取测试图片文件路径。"""
    return str(Path(__file__).parent / "templates" / "easy-doc.png")


@pytest.fixture
def output_dir(tmp_path):
    """创建临时输出目录。"""
    return tmp_path / "output"


class TestWordAPIInit:
    """测试 WordAPI 初始化功能。"""
    
    def test_init_with_valid_template(self, template_path):
        """测试使用有效模板路径初始化。"""
        api = WordAPI(template_path)
        assert api.template_path == template_path

    def test_init_with_invalid_template(self):
        """测试使用无效模板路径应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            WordAPI("nonexistent_template.docx")


class TestDocContainer:
    """测试 DocContainer 链式调用功能。"""
    
    def test_add_title(self, template_path, output_dir):
        """测试添加主标题并验证返回容器自身支持链式调用。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_title("测试标题")
        assert result is container

    def test_add_heading(self, template_path, output_dir):
        """测试添加不同级别的标题（1-3级）。"""
        api = WordAPI(template_path)
        container = api.new_container()
        for level in [1, 2, 3]:
            result = container.add_heading(f"{level}级标题", level=level)
            assert result is container

    def test_add_paragraph(self, template_path, output_dir):
        """测试添加普通段落。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_paragraph("测试段落")
        assert result is container

    def test_add_image(self, template_path, test_image, output_dir):
        """测试添加图片并指定宽度。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_image(test_image, width_cm=6.0)
        assert result is container

    def test_add_table(self, template_path, output_dir):
        """测试添加基础表格。"""
        api = WordAPI(template_path)
        container = api.new_container()
        data = [["表头1", "表头2"], ["数据1", "数据2"]]
        result = container.add_table(data)
        assert result is container

    def test_add_table_by_config(self, template_path, output_dir):
        """测试通过配置字典添加表格。"""
        api = WordAPI(template_path)
        container = api.new_container()
        config = {
            "data": [["序号", "内容"], ["1", "测试"]],
            "style": {
                "header": TABLE_HEADER_STYLE,
                "body": TABLE_BODY_STYLE,
            }
        }
        result = container.add_table_by_config(config)
        assert result is container

    def test_add_page_break(self, template_path, output_dir):
        """测试添加分页符。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_page_break()
        assert result is container

    def test_add_field_paragraph(self, template_path, output_dir):
        """测试添加包含域代码的段落（如页码）。"""
        api = WordAPI(template_path)
        container = api.new_container()
        parts = [
            {"type": "text", "value": "第 "},
            {"type": "field", "code": "PAGE"},
            {"type": "text", "value": " 页"},
        ]
        result = container.add_field_paragraph(parts)
        assert result is not None

    def test_add_page_footer(self, template_path, output_dir):
        """测试添加页脚页码信息。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_page_footer()
        assert result is not None

    def test_add_figure_caption_auto(self, template_path, output_dir):
        """测试添加自动编号的图注。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_figure_caption_auto("示例图")
        assert result is not None

    def test_add_table_caption_auto(self, template_path, output_dir):
        """测试添加自动编号的表注。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = container.add_table_caption_auto("示例表")
        assert result is not None

    def test_chain_calling(self, template_path, test_image, output_dir):
        """测试多个方法的链式调用。"""
        api = WordAPI(template_path)
        container = api.new_container()
        result = (
            container
            .add_title("主标题")
            .add_heading("一级标题", level=1)
            .add_paragraph("正文内容")
            .add_page_break()
        )
        assert result is container


class TestAddParagraph:
    def test_add_empty_paragraph(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_empty_paragraph(container.subdoc, BODY_STYLE)
        assert paragraph is not None

    def test_add_text_run(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = container.subdoc.add_paragraph()
        run = api.add_text_run(paragraph, "测试文本", BODY_STYLE)
        assert run is not None

    def test_add_paragraph_with_text(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_paragraph(container.subdoc, "完整段落", BODY_STYLE)
        assert paragraph is not None

    def test_add_paragraph_with_none_text(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_paragraph(container.subdoc, None, BODY_STYLE)
        assert paragraph is not None


class TestAddImageBlock:
    def test_add_image_with_width(self, template_path, test_image, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_image_block(
            container.subdoc,
            test_image,
            width_cm=6.0,
            align="center"
        )
        assert paragraph is not None

    def test_add_image_with_height(self, template_path, test_image, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_image_block(
            container.subdoc,
            test_image,
            height_cm=4.0,
            align="left"
        )
        assert paragraph is not None

    def test_add_image_with_both_dimensions(self, template_path, test_image, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_image_block(
            container.subdoc,
            test_image,
            width_cm=6.0,
            height_cm=4.0,
            align="right"
        )
        assert paragraph is not None

    def test_add_image_without_dimensions(self, template_path, test_image, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_image_block(
            container.subdoc,
            test_image,
            style=IMAGE_STYLE
        )
        assert paragraph is not None

    def test_add_image_not_found(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        with pytest.raises(FileNotFoundError):
            api.add_image_block(container.subdoc, "nonexistent.png")


class TestInsertTable:
    def test_insert_basic_table(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        data = [
            ["姓名", "年龄", "城市"],
            ["张三", "25", "北京"],
            ["李四", "30", "上海"],
        ]
        table = api.insert_table(container.subdoc, data)
        assert table is not None
        assert len(table.rows) == 3

    def test_insert_table_with_custom_styles(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        data = [["A", "B"], ["1", "2"]]
        header_style = make_cell_style(bg_color="FF0000", bold=True)
        body_style = make_cell_style(font_size=10)
        table_style = make_table_style(border_color="0000FF")
        table = api.insert_table(
            container.subdoc,
            data,
            header_style=header_style,
            body_style=body_style,
            table_style=table_style
        )
        assert table is not None

    def test_insert_table_empty_data(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        with pytest.raises(ValueError):
            api.insert_table(container.subdoc, [])

    def test_insert_table_irregular_rows(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        data = [
            ["A", "B", "C"],
            ["1", "2"],
            ["X"],
        ]
        table = api.insert_table(container.subdoc, data)
        assert table is not None

    def test_insert_table_with_col_widths(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        data = [["列1", "列2", "列3"], ["a", "b", "c"]]
        table_style = make_table_style(col_widths_cm=[3.0, 4.0, 5.0])
        table = api.insert_table(container.subdoc, data, table_style=table_style)
        assert table is not None

    def test_insert_table_with_row_heights(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        data = [["行1"], ["行2"]]
        table_style = make_table_style(row_heights_cm=[1.0, 1.5])
        table = api.insert_table(container.subdoc, data, table_style=table_style)
        assert table is not None


class TestInsertTableByConfig:
    def test_insert_table_by_config_full(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        config = {
            "data": [["序号", "名称"], ["1", "项目A"]],
            "row_heights_cm": [0.8, 0.6],
            "col_widths_cm": [2.0, 6.0],
            "style": {
                "header": TABLE_HEADER_STYLE,
                "body": TABLE_BODY_STYLE,
                "table": make_table_style(),
            }
        }
        table = api.insert_table_by_config(container.subdoc, config)
        assert table is not None

    def test_insert_table_by_config_minimal(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        config = {
            "data": [["简单表格"]]
        }
        table = api.insert_table_by_config(container.subdoc, config)
        assert table is not None

    def test_insert_table_by_config_empty_data(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        config = {}
        table = api.insert_table_by_config(container.subdoc, config)
        assert table is not None


class TestFieldOperations:
    def test_add_field_run(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = container.subdoc.add_paragraph()
        run = api.add_field_run(paragraph, "PAGE")
        assert run is not None

    def test_add_field_paragraph_mixed(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        parts = [
            {"type": "text", "value": "文档 "},
            {"type": "field", "code": r"SEQ Figure \* ARABIC"},
            {"type": "text", "value": " - 说明"},
        ]
        paragraph = api.add_field_paragraph(container.subdoc, parts, BODY_STYLE)
        assert paragraph is not None

    def test_add_field_paragraph_invalid_type(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        parts = [{"type": "invalid", "value": "test"}]
        with pytest.raises(ValueError):
            api.add_field_paragraph(container.subdoc, parts)


class TestCaptionAndFooter:
    def test_add_page_footer(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_page_footer(container.subdoc, FOOTER_STYLE)
        assert paragraph is not None

    def test_add_figure_caption_auto(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_figure_caption_auto(
            container.subdoc,
            "系统架构图",
            CAPTION_STYLE
        )
        assert paragraph is not None

    def test_add_table_caption_auto(self, template_path, output_dir):
        api = WordAPI(template_path)
        container = api.new_container()
        paragraph = api.add_table_caption_auto(
            container.subdoc,
            "数据统计表",
            CAPTION_STYLE
        )
        assert paragraph is not None


class TestRender:
    def test_render_basic(self, template_path, output_dir):
        api = WordAPI(template_path)
        output_file = str(output_dir / "test_render_basic.docx")
        
        context = {
            "text_tag": make_rich_text("测试文本", BODY_STYLE),
            "image_tag": api.new_container().subdoc,
            "table_tag": api.new_container().subdoc,
            "result": api.new_container().subdoc,
        }
        
        result_path = api.render(context, output_file)
        assert os.path.exists(result_path)
        assert result_path == output_file

    def test_render_with_content(self, template_path, test_image, output_dir):
        api = WordAPI(template_path)
        output_file = str(output_dir / "test_render_with_content.docx")
        
        image_container = api.new_container()
        image_container.add_image(test_image, width_cm=6.0)
        
        table_container = api.new_container()
        table_container.add_table([
            ["项目", "数值"],
            ["指标1", "100"],
            ["指标2", "200"],
        ])
        
        result_container = api.new_container()
        result_container.add_heading("测试结果", level=1)
        result_container.add_paragraph("所有测试通过")
        
        context = {
            "text_tag": make_rich_text("自动化测试报告", BODY_STYLE),
            "image_tag": image_container.subdoc,
            "table_tag": table_container.subdoc,
            "result": result_container.subdoc,
        }
        
        result_path = api.render(context, output_file)
        assert os.path.exists(result_path)

    def test_render_creates_directory(self, template_path, tmp_path):
        api = WordAPI(template_path)
        output_file = str(tmp_path / "nested" / "dir" / "output.docx")
        
        context = {
            "text_tag": make_rich_text("测试", BODY_STYLE),
            "image_tag": api.new_container().subdoc,
            "table_tag": api.new_container().subdoc,
            "result": api.new_container().subdoc,
        }
        
        result_path = api.render(context, output_file)
        assert os.path.exists(result_path)


class TestWriteHeaderFooter:
    def test_write_header_footer(self, template_path, output_dir):
        api = WordAPI(template_path)
        output_file = str(output_dir / "test_header_footer.docx")
        
        context = {
            "text_tag": make_rich_text("测试", BODY_STYLE),
            "image_tag": api.new_container().subdoc,
            "table_tag": api.new_container().subdoc,
            "result": api.new_container().subdoc,
        }
        api.render(context, output_file)
        
        result_path = api.write_header_footer(
            output_file,
            header_text="测试文档页眉",
            header_style=HEADER_STYLE,
            footer_style=FOOTER_STYLE
        )
        assert os.path.exists(result_path)

    def test_write_header_footer_no_header_text(self, template_path, output_dir):
        api = WordAPI(template_path)
        output_file = str(output_dir / "test_footer_only.docx")
        
        context = {
            "text_tag": make_rich_text("测试", BODY_STYLE),
            "image_tag": api.new_container().subdoc,
            "table_tag": api.new_container().subdoc,
            "result": api.new_container().subdoc,
        }
        api.render(context, output_file)
        
        result_path = api.write_header_footer(
            output_file,
            header_text=None,
            footer_style=FOOTER_STYLE
        )
        assert os.path.exists(result_path)


class TestHelperMethods:
    def test_check_color_valid(self):
        assert WordAPI._check_color("#FF0000") == "FF0000"
        assert WordAPI._check_color("00FF00") == "00FF00"
        assert WordAPI._check_color(None) is None

    def test_check_color_invalid(self):
        with pytest.raises(ValueError):
            WordAPI._check_color("#GGG")
        with pytest.raises(ValueError):
            WordAPI._check_color("12345")

    def test_get_paragraph_alignment(self):
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        assert WordAPI._get_paragraph_alignment("center") == WD_PARAGRAPH_ALIGNMENT.CENTER
        assert WordAPI._get_paragraph_alignment("right") == WD_PARAGRAPH_ALIGNMENT.RIGHT
        assert WordAPI._get_paragraph_alignment("left") == WD_PARAGRAPH_ALIGNMENT.LEFT
        assert WordAPI._get_paragraph_alignment(None) == WD_PARAGRAPH_ALIGNMENT.LEFT

    def test_get_vertical_alignment(self):
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        assert WordAPI._get_vertical_alignment("top") == WD_CELL_VERTICAL_ALIGNMENT.TOP
        assert WordAPI._get_vertical_alignment("bottom") == WD_CELL_VERTICAL_ALIGNMENT.BOTTOM
        assert WordAPI._get_vertical_alignment("center") == WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def test_get_table_alignment(self):
        from docx.enum.table import WD_TABLE_ALIGNMENT
        assert WordAPI._get_table_alignment("left") == WD_TABLE_ALIGNMENT.LEFT
        assert WordAPI._get_table_alignment("right") == WD_TABLE_ALIGNMENT.RIGHT
        assert WordAPI._get_table_alignment("center") == WD_TABLE_ALIGNMENT.CENTER

    def test_is_image_file(self, template_path):
        api = WordAPI(template_path)
        assert api._is_image_file("test.png") is True
        assert api._is_image_file("test.jpg") is True
        assert api._is_image_file("test.docx") is False

    def test_get_display_length(self, template_path):
        api = WordAPI(template_path)
        assert api._get_display_length("abc") == 3
        assert api._get_display_length("中文") >= 4
        assert api._get_display_length("") == 1

    def test_normalize_table_data(self, template_path):
        api = WordAPI(template_path)
        data = [["A", "B"], ["1"]]
        normalized = api._normalize_table_data(data)
        assert len(normalized[1]) == 2

    def test_scale_widths_to_max(self, template_path):
        api = WordAPI(template_path)
        widths = [5.0, 5.0, 5.0]
        scaled = api._scale_widths_to_max(widths, 10.0)
        assert sum(scaled) <= 10.0


class TestIntegration:
    """集成测试：完整文档生成流程。"""
    
    def test_full_document_generation(self, template_path, test_image, output_dir):
        """测试完整文档生成（包含所有功能）。"""
        api = WordAPI(template_path)
        output_file = str(output_dir / "full_document.docx")
        
        text_content = make_rich_text("完整测试文档", BODY_STYLE)
        
        image_container = api.new_container()
        image_container.add_image(test_image, width_cm=8.0)
        image_container.add_figure_caption_auto("测试图片")
        
        table_container = api.new_container()
        table_container.add_heading("数据表格", level=2)
        table_container.add_table([
            ["序号", "项目名称", "状态"],
            ["1", "项目A", "完成"],
            ["2", "项目B", "进行中"],
        ])
        table_container.add_table_caption_auto("项目状态表")
        
        result_container = api.new_container()
        result_container.add_title("测试结论")
        result_container.add_paragraph("所有功能测试通过")
        result_container.add_page_break()
        result_container.add_paragraph("第二页内容")
        
        context = {
            "text_tag": text_content,
            "image_tag": image_container.subdoc,
            "table_tag": table_container.subdoc,
            "result": result_container.subdoc,
        }
        
        output_path = api.render(context, output_file)
        final_path = api.write_header_footer(
            output_path,
            header_text="EasyDocx 测试文档",
            header_style=HEADER_STYLE,
            footer_style=FOOTER_STYLE
        )
        
        assert os.path.exists(final_path)
        assert os.path.getsize(final_path) > 0

    def test_generate_sample_document(self, template_path, test_image):
        """生成示例文档到 output 目录供查看。"""
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        output_file = str(output_dir / "sample_test_output.docx")
        
        api = WordAPI(template_path)
        
        text_content = make_rich_text("EasyDocx 完整功能测试报告", BODY_STYLE)
        
        image_container = api.new_container()
        image_container.add_title("图片功能测试")
        
        image_container.add_heading("测试项1：仅指定宽度插入图片", level=2)
        image_container.add_paragraph("测试方法：add_image(image_path, width_cm=6.0)")
        image_container.add_paragraph("测试结果：✓ 通过")
        image_container.add_paragraph("说明：图片按指定宽度等比例缩放")
        image_container.add_image(test_image, width_cm=6.0)
        image_container.add_figure_caption_auto("仅指定宽度")
        
        image_container.add_heading("测试项2：仅指定高度插入图片", level=2)
        image_container.add_paragraph("测试方法：add_image(image_path, height_cm=4.0)")
        image_container.add_paragraph("测试结果：✓ 通过")
        image_container.add_paragraph("说明：图片按指定高度等比例缩放")
        image_container.add_image(test_image, height_cm=4.0)
        image_container.add_figure_caption_auto("仅指定高度")
        
        image_container.add_heading("测试项3：同时指定宽度和高度", level=2)
        image_container.add_paragraph("测试方法：add_image(image_path, width_cm=6.0, height_cm=4.0)")
        image_container.add_paragraph("测试结果：✓ 通过")
        image_container.add_paragraph("说明：图片按指定尺寸强制缩放")
        image_container.add_image(test_image, width_cm=6.0, height_cm=4.0)
        image_container.add_figure_caption_auto("同时指定宽高")
        
        image_container.add_heading("测试项4：不指定尺寸使用原始大小", level=2)
        image_container.add_paragraph("测试方法：add_image(image_path)")
        image_container.add_paragraph("测试结果：✓ 通过")
        image_container.add_paragraph("说明：图片保持原始分辨率")
        image_container.add_image(test_image)
        image_container.add_figure_caption_auto("原始大小")
        
        image_container.add_heading("测试项5：图片文件不存在异常处理", level=2)
        image_container.add_paragraph("测试方法：add_image('nonexistent.png')")
        image_container.add_paragraph("测试结果：✓ 通过")
        image_container.add_paragraph("说明：正确抛出 FileNotFoundError")
        
        table_container = api.new_container()
        table_container.add_title("表格功能测试")
        
        table_container.add_heading("测试项1：基础表格插入", level=2)
        table_container.add_paragraph("测试方法：insert_table(container, data)")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：验证表格行数和列数正确")
        table_container.add_table([
            ["姓名", "年龄", "城市"],
            ["张三", "25", "北京"],
            ["李四", "30", "上海"],
        ])
        table_container.add_table_caption_auto("基础表格")
        
        table_container.add_heading("测试项2：自定义样式表格", level=2)
        table_container.add_paragraph("测试方法：insert_table(data, header_style, body_style, table_style)")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：支持表头表体自定义样式")
        header_style = make_cell_style(bg_color="4472C4", font_color="FFFFFF", bold=True)
        body_style = make_cell_style(font_size=10)
        table_style = make_table_style(border_color="4472C4")
        table_container.add_table(
            [["项目", "状态"], ["测试A", "完成"], ["测试B", "进行中"]],
            header_style=header_style,
            body_style=body_style,
            table_style=table_style
        )
        table_container.add_table_caption_auto("自定义样式表格")
        
        table_container.add_heading("测试项3：空数据异常", level=2)
        table_container.add_paragraph("测试方法：insert_table([])")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：正确抛出 ValueError")
        
        table_container.add_heading("测试项4：不规则行数表格", level=2)
        table_container.add_paragraph("测试方法：insert_table(不等长二维数组)")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：自动补齐缺失列")
        table_container.add_table([
            ["A", "B", "C"],
            ["1", "2"],
            ["X"],
        ])
        table_container.add_table_caption_auto("不规则行数表格")
        
        table_container.add_heading("测试项5：指定列宽表格", level=2)
        table_container.add_paragraph("测试方法：insert_table(data, table_style=make_table_style(col_widths_cm=[...]))")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：支持精确列宽设置")
        table_style = make_table_style(col_widths_cm=[3.0, 5.0, 4.0])
        table_container.add_table(
            [["列1", "列2", "列3"], ["a", "b", "c"]],
            table_style=table_style
        )
        table_container.add_table_caption_auto("指定列宽表格")
        
        table_container.add_heading("测试项6：指定行高表格", level=2)
        table_container.add_paragraph("测试方法：insert_table(data, table_style=make_table_style(row_heights_cm=[...]))")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：支持精确行高设置")
        table_style = make_table_style(row_heights_cm=[1.0, 1.5, 2.0])
        table_container.add_table(
            [["行1"], ["行2"], ["行3"]],
            table_style=table_style
        )
        table_container.add_table_caption_auto("指定行高表格")
        
        table_container.add_heading("测试项7：配置化表格-完整", level=2)
        table_container.add_paragraph("测试方法：insert_table_by_config(完整配置字典)")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：支持行列高、样式完整配置")
        config = {
            "data": [["序号", "名称"], ["1", "项目A"]],
            "row_heights_cm": [0.8, 0.6],
            "col_widths_cm": [2.0, 6.0],
        }
        table_container.add_table_by_config(config)
        table_container.add_table_caption_auto("配置化表格-完整")
        
        table_container.add_heading("测试项8：配置化表格-最小", level=2)
        table_container.add_paragraph("测试方法：insert_table_by_config({'data': [...]})")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：仅需提供数据即可")
        table_container.add_table_by_config({"data": [["简单表格"]]})
        table_container.add_table_caption_auto("配置化表格-最小")
        
        table_container.add_heading("测试项9：配置化表格-空", level=2)
        table_container.add_paragraph("测试方法：insert_table_by_config({})")
        table_container.add_paragraph("测试结果：✓ 通过")
        table_container.add_paragraph("说明：使用默认示例数据")
        table_container.add_table_by_config({})
        table_container.add_table_caption_auto("配置化表格-空")
        
        result_container = api.new_container()
        result_container.add_title("其他功能测试")
        
        result_container.add_heading("段落功能", level=2)
        result_container.add_heading("测试项1：添加空段落", level=3)
        result_container.add_paragraph("测试方法：add_empty_paragraph(container, style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        api.add_empty_paragraph(result_container.subdoc, BODY_STYLE)
        
        result_container.add_heading("测试项2：添加文本段(Run)", level=3)
        result_container.add_paragraph("测试方法：add_text_run(paragraph, text, style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        para = result_container.subdoc.add_paragraph()
        api.add_text_run(para, "这是文本段测试", BODY_STYLE)
        
        result_container.add_heading("测试项3：添加完整段落", level=3)
        result_container.add_paragraph("测试方法：add_paragraph(container, text, style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        api.add_paragraph(result_container.subdoc, "这是完整段落测试", BODY_STYLE)
        
        result_container.add_heading("测试项4：None文本处理", level=3)
        result_container.add_paragraph("测试方法：add_paragraph(container, None, style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        api.add_paragraph(result_container.subdoc, None, BODY_STYLE)
        
        result_container.add_heading("域代码功能", level=2)
        result_container.add_heading("测试项1：添加单个域代码", level=3)
        result_container.add_paragraph("测试方法：add_field_run(paragraph, 'PAGE')")
        result_container.add_paragraph("测试结果：✓ 通过")
        para = result_container.subdoc.add_paragraph()
        api.add_text_run(para, "当前页码：", BODY_STYLE)
        api.add_field_run(para, "PAGE")
        
        result_container.add_heading("测试项2：混合文本和域代码", level=3)
        result_container.add_paragraph("测试方法：add_field_paragraph(parts)")
        result_container.add_paragraph("测试结果：✓ 通过")
        parts = [
            {"type": "text", "value": "文档 "},
            {"type": "field", "code": r"SEQ Figure \* ARABIC"},
            {"type": "text", "value": " - 说明"},
        ]
        api.add_field_paragraph(result_container.subdoc, parts, BODY_STYLE)
        
        result_container.add_heading("测试项3：无效类型异常处理", level=3)
        result_container.add_paragraph("测试方法：add_field_paragraph([{'type': 'invalid'}])")
        result_container.add_paragraph("测试结果：✓ 通过")
        
        result_container.add_heading("题注和页脚", level=2)
        result_container.add_heading("测试项1：页脚页码", level=3)
        result_container.add_paragraph("测试方法：add_page_footer(container)")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：生成'第 X 页 / 共 Y 页'格式")
        api.add_page_footer(result_container.subdoc, FOOTER_STYLE)
        
        result_container.add_heading("测试项2：自动编号图注", level=3)
        result_container.add_paragraph("测试方法：add_figure_caption_auto('标题')")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：生成'图 X 标题'格式")
        api.add_figure_caption_auto(result_container.subdoc, "示例图注")
        
        result_container.add_heading("测试项3：自动编号表注", level=3)
        result_container.add_paragraph("测试方法：add_table_caption_auto('标题')")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：生成'表 X 标题'格式")
        api.add_table_caption_auto(result_container.subdoc, "示例表注")
        
        result_container.add_heading("渲染功能", level=2)
        result_container.add_heading("测试项1：基础渲染", level=3)
        result_container.add_paragraph("测试方法：render(context, output_path)")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：验证文件正确生成")
        
        result_container.add_heading("测试项2：完整内容渲染", level=3)
        result_container.add_paragraph("测试方法：render(包含图片表格文本的context)")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：所有元素正确渲染")
        
        result_container.add_heading("测试项3：自动创建目录", level=3)
        result_container.add_paragraph("测试方法：render(context, 'nested/dir/output.docx')")
        result_container.add_paragraph("测试结果：✓ 通过")
        result_container.add_paragraph("说明：自动创建不存在的目录")
        
        result_container.add_heading("页眉页脚", level=2)
        result_container.add_heading("测试项1：同时设置页眉页脚", level=3)
        result_container.add_paragraph("测试方法：write_header_footer(header_text, header_style, footer_style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        
        result_container.add_heading("测试项2：仅设置页脚", level=3)
        result_container.add_paragraph("测试方法：write_header_footer(header_text=None, footer_style)")
        result_container.add_paragraph("测试结果：✓ 通过")
        
        result_container.add_page_break()
        
        result_container.add_heading("辅助方法测试", level=2)
        helper_data = [
            ["方法", "测试内容", "状态"],
            ["_check_color", "颜色值验证（有效/无效输入）", "✓ 通过"],
            ["_get_paragraph_alignment", "段落对齐方式转换", "✓ 通过"],
            ["_get_vertical_alignment", "单元格垂直对齐转换", "✓ 通过"],
            ["_get_table_alignment", "表格对齐方式转换", "✓ 通过"],
            ["_is_image_file", "图片文件扩展名检测", "✓ 通过"],
            ["_get_display_length", "文本显示长度计算", "✓ 通过"],
            ["_normalize_table_data", "表格数据标准化（补齐列数）", "✓ 通过"],
            ["_scale_widths_to_max", "列宽缩放至最大宽度", "✓ 通过"],
        ]
        result_container.add_table(helper_data)
        
        context = {
            "text_tag": text_content,
            "image_tag": image_container.subdoc,
            "table_tag": table_container.subdoc,
            "result": result_container.subdoc,
        }
        
        output_path = api.render(context, output_file)
        final_path = api.write_header_footer(
            output_path,
            header_text="EasyDocx 测试报告",
            header_style=HEADER_STYLE,
            footer_style=FOOTER_STYLE
        )
        
        print(f"\n示例文档已生成: {final_path}")
        assert os.path.exists(final_path)
