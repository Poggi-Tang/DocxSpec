"""Read the Studio's default chapter structure from the packaged Word master."""

from docxspec._section_templates import load_ds_section

HEADING_STYLES = [f"DS{label}级标题" for label in "一二三四五六"]


def master_document():
    body = load_ds_section("body")
    cover = load_ds_section("cover")
    revision = load_ds_section("revision")
    sections = ["封面", "修改记录", "目录", "图目录", "表目录"]
    metadata = [
        {"kind": kind, "level": 0}
        for kind in ("cover", "revision", "toc", "figures", "tables")
    ]
    texts = {"0": "\n".join(
        p.text for p in cover.paragraphs
        if p.text.strip() in ("XXXX系统", "技术方案")
    )}
    in_body = False
    first_case_section = None
    for paragraph in body.paragraphs:
        if paragraph.style.name == HEADING_STYLES[0]:
            in_body = True
        if not in_body:
            continue
        if paragraph.style.name in HEADING_STYLES:
            level = HEADING_STYLES.index(paragraph.style.name) + 1
            kind = "heading"
            if level == 6 and first_case_section is None:
                first_case_section = len(sections)
                kind = "cases"
            sections.append(paragraph.text.strip())
            metadata.append({"kind": kind, "level": level})
            texts[str(len(sections) - 1)] = ""
        elif paragraph.style.name == "DS正文" and paragraph.text.strip():
            index = str(len(sections) - 1)
            texts[index] += paragraph.text.strip() + "\n"

    document = dict(
        schema="docxspec-studio-v1", sections=sections, section_meta=metadata,
        section=first_case_section if first_case_section is not None else 0,
        selected=0, intro=texts.get(str(first_case_section), "").strip(),
        texts=texts, format={}, source="测试用例",
        repeat="每条记录", empty="隐藏区块", cases=[
            dict(id="TC-001", name="测试用例示例", steps=["填写测试步骤"],
                 expected="填写预期结果", actual="待执行", result="待执行"),
            dict(id="TC-002", name="第二个测试用例示例", steps=["填写测试步骤"],
                 expected="填写预期结果", actual="待执行", result="待执行"),
        ],
    )
    return dict(
        document=document,
        revision_rows=[[cell.text for cell in row.cells] for row in revision.tables[0].rows],
        signature_rows=[[cell.text for cell in row.cells] for row in cover.tables[0].rows],
        file_number=next(p.text for p in cover.paragraphs if "文件编号" in p.text),
        template="body.docx",
    )
