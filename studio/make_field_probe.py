"""Create controlled stale-field fixture; separate from Studio's exported report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from docxspec import ensure_ds_styles, mark_update_fields_on_open


def field(paragraph, code, cache):
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    paragraph.add_run()._r.append(begin)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = code
    paragraph.add_run()._r.append(instr)
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    paragraph.add_run()._r.append(sep)
    paragraph.add_run(cache)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(end)


def main():
    out = Path(__file__).resolve().parent / "evidence/acceptance/field-probe.docx"
    doc = Document()
    ensure_ds_styles(doc)
    doc.core_properties.author = "DocxSpec"
    doc.core_properties.title = "DS field acceptance"
    doc.add_paragraph("DS Field Acceptance", style="DS主标题")
    doc.add_paragraph(
        "All field caches intentionally start stale. Expected: sequence 1, 2; "
        "reference 1; page count 2; TOC with two headings."
    )
    field(doc.add_paragraph(), r'TOC \o "1-2" \h \z \u', "STALE TOC")
    doc.add_paragraph("First section", style="DS一级标题")
    p = doc.add_paragraph("Figure ")
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "42")
    start.set(qn("w:name"), "DSFirstFigure")
    p._p.append(start)
    field(p, r"SEQ DSFigure \* ARABIC", "999")
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "42")
    p._p.append(end)
    p.add_run(" first caption")
    p = doc.add_paragraph("Figure ")
    field(p, r"SEQ DSFigure \* ARABIC", "999")
    p.add_run(" second caption")
    p = doc.add_paragraph("Reference to first figure: ")
    field(p, r"REF DSFirstFigure \h", "999")
    doc.add_page_break()
    doc.add_paragraph("Second section", style="DS一级标题")
    doc.add_paragraph("Second page content.")
    p = doc.sections[0].footer.paragraphs[0]
    p.style = "DS页脚"
    p.add_run("Page ")
    field(p, "PAGE", "999")
    p.add_run(" of ")
    field(p, "NUMPAGES", "999")
    out.parent.mkdir(exist_ok=True, parents=True)
    doc.save(out)
    mark_update_fields_on_open(out)
    print(out)


if __name__ == "__main__":
    main()
