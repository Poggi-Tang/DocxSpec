"""Carry the built-in DS style library into every generated Word document."""

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from ._xml_order import place_before

_PRIORITY_SUCCESSORS = (
    "w:semiHidden", "w:unhideWhenUsed", "w:qFormat", "w:locked", "w:personal",
    "w:personalCompose", "w:personalReply", "w:rsid", "w:pPr", "w:rPr",
    "w:tblPr", "w:trPr", "w:tcPr", "w:tblStylePr",
)


def _normalize_priority(style):
    priority = style.find(qn("w:uiPriority"))
    if priority is not None:
        place_before(style, priority, _PRIORITY_SUCCESSORS)


def ensure_ds_styles(document):
    """Add missing master styles and numbering without replacing caller styles.

    Unused styles are included for subsequent manual editing. Style IDs and
    numbering IDs are remapped so existing custom templates keep their references.
    """
    master = Document(Path(__file__).parent / "assets" / "docxspec_master_template.docx")
    names = {}
    for style in document.styles:
        _normalize_priority(style.element)
        names[style.name] = style.style_id
    if all(style.name in names for style in master.styles if style.name.startswith("DS")):
        return

    used_ids = {style.style_id for style in document.styles}
    mapping = {}
    additions = []
    for style in master.styles:
        if style.name in names:
            mapping[style.style_id] = names[style.name]
            continue
        target_id = style.style_id
        while target_id in used_ids:
            target_id = "DSMaster" + target_id
        used_ids.add(target_id)
        mapping[style.style_id] = target_id
        element = deepcopy(style.element)
        element.set(qn("w:styleId"), target_id)
        _normalize_priority(element)
        additions.append(element)

    # Import the master's numbering only when a new style needs it. Existing
    # template lists keep their original IDs and definitions.
    number_mapping = {}
    if any(element.xpath(".//w:numId") for element in additions):
        source = master.part.numbering_part.element
        target = document.part.numbering_part.element
        next_num = max(
            (int(e.get(qn("w:numId"))) for e in target.findall(qn("w:num"))), default=0
        ) + 1
        next_abstract = max(
            (int(e.get(qn("w:abstractNumId"))) for e in target.findall(qn("w:abstractNum"))),
            default=-1,
        ) + 1
        abstract_mapping = {}
        for element in source.findall(qn("w:abstractNum")):
            copy = deepcopy(element)
            original = element.get(qn("w:abstractNumId"))
            abstract_mapping[original] = str(next_abstract)
            copy.set(qn("w:abstractNumId"), str(next_abstract))
            for reference in copy.iter(
                qn("w:pStyle"), qn("w:rStyle"), qn("w:styleLink"), qn("w:numStyleLink")
            ):
                reference.set(qn("w:val"), mapping[reference.get(qn("w:val"))])
            first_num = target.find(qn("w:num"))
            if first_num is None:
                target.append(copy)
            else:
                first_num.addprevious(copy)
            next_abstract += 1
        for element in source.findall(qn("w:num")):
            copy = deepcopy(element)
            number_mapping[element.get(qn("w:numId"))] = str(next_num)
            copy.set(qn("w:numId"), str(next_num))
            reference = copy.find(qn("w:abstractNumId"))
            reference.set(qn("w:val"), abstract_mapping[reference.get(qn("w:val"))])
            target.append(copy)
            next_num += 1

    for element in additions:
        for reference in element.xpath("./w:basedOn|./w:next|./w:link"):
            reference.set(qn("w:val"), mapping[reference.get(qn("w:val"))])
        for reference in element.xpath(".//w:numId"):
            reference.set(qn("w:val"), number_mapping[reference.get(qn("w:val"))])
        document.styles.element.append(element)
