"""Assemble standalone DS front-matter templates in a shared Word document."""

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import PartFactory
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docxcompose.composer import Composer

from ._field_xml import field_instruction, iter_fields
from ._master_lists import (
    FIGURE_CAPTION_LABELS,
    TABLE_CAPTION_LABELS,
    caption_label_matches,
    caption_labels,
    list_field_label,
)
from ._xml_order import child_in_order

DEFAULT_DS_SECTIONS = Path(__file__).resolve().parent / "assets" / "ds_sections"
_STORIES = (
    "header",
    "even_page_header",
    "first_page_header",
    "footer",
    "even_page_footer",
    "first_page_footer",
)
_NUMBER_SUCCESSORS = (
    "w:cols",
    "w:formProt",
    "w:vAlign",
    "w:noEndnote",
    "w:titlePg",
    "w:textDirection",
    "w:bidi",
    "w:rtlGutter",
    "w:docGrid",
    "w:printerSettings",
    "w:sectPrChange",
)
_FRONT_BLOCKS = ("cover", "revision", "contents", "figures", "tables")


def load_ds_section(name, directory=None):
    filename = f"{name}.docx"
    custom = Path(directory) / filename if directory is not None else None
    path = custom if custom is not None and custom.is_file() else DEFAULT_DS_SECTIONS / filename
    return Document(path)


def _materialize_stories(section):
    # A standalone block with an omitted header means an empty header. Make it
    # explicit before assembling, where omission would link to the previous block.
    for name in _STORIES:
        story = getattr(section, name)
        if story.is_linked_to_previous:
            story.is_linked_to_previous = False


def _read_front_blocks(body, directory):
    labels = caption_labels(body)
    for name in _FRONT_BLOCKS:
        relevant = {"figures": FIGURE_CAPTION_LABELS, "tables": TABLE_CAPTION_LABELS}.get(name)
        if relevant is not None and labels.isdisjoint(relevant):
            continue
        block = load_ds_section(name, directory)
        if len(block.sections) != 1:
            raise ValueError(f"{name}.docx 必须包含一个 Word 分节，可排成多页")
        if relevant is not None:
            targets = {
                list_field_label(field_instruction(owner, runs))
                for owner, _, runs in iter_fields(block.element.body)
            }
            if not any(caption_label_matches(label, labels) for label in targets & relevant):
                continue
        yield name, block


def _copy_part(relation, package, occupied, copied, block_name):
    if relation.is_external:
        return relation.target_ref
    original = relation.target_part
    if original in copied:
        return copied[original]
    name = PackURI(f"/word/ds_sections/{block_name}/{original.partname.membername}")
    if name in occupied:
        stem, dot, extension = name.rpartition(".")
        number = 1
        while name in occupied:
            name = PackURI(f"{stem}-{number}{dot}{extension}")
            number += 1
    occupied.add(name)
    clone = PartFactory(name, original.content_type, relation.reltype, original.blob, package)
    copied[original] = clone
    for child in original.rels.values():
        target = _copy_part(child, package, occupied, copied, block_name)
        clone.load_rel(child.reltype, target, child.rId, child.is_external)
    return clone


def _section_properties(document, block_name, block, composer):
    section = block.sections[0]
    _materialize_stories(section)
    properties = deepcopy(section._sectPr)
    properties.start_type = WD_SECTION_START.NEW_PAGE
    package = document.part.package
    occupied = {part.partname for part in package.iter_parts()}
    copied = {}
    for reference in properties.xpath(".//*[@r:id]"):
        relation = block.part.rels[reference.get(qn("r:id"))]
        part = _copy_part(relation, package, occupied, copied, block_name)
        if relation.reltype in {RT.HEADER, RT.FOOTER}:
            composer.add_styles(block, part.element)
            composer.add_numberings(block, part.element)
        rid = document.part.relate_to(part, relation.reltype, relation.is_external)
        reference.set(qn("r:id"), rid)

    if block_name in {"contents", "figures", "tables"}:
        numbering = child_in_order(properties, "w:pgNumType", _NUMBER_SUCCESSORS)
        numbering.set(qn("w:fmt"), "upperRoman")
        if block_name == "contents":
            numbering.set(qn("w:start"), "1")
        else:
            numbering.attrib.pop(qn("w:start"), None)
    return properties


def assemble_ds_front_matter(document, *, directory=None, prepare_cover=None, header_title=None):
    """Prepend DS blocks, selecting the optional lists from the final body captions."""
    body = document.element.body
    blocks = list(_read_front_blocks(body, directory))
    first_body_section = document.sections[0]
    _materialize_stories(first_body_section)
    first_body_section.start_type = WD_SECTION_START.NEW_PAGE
    numbering = child_in_order(first_body_section._sectPr, "w:pgNumType", _NUMBER_SUCCESSORS)
    numbering.set(qn("w:fmt"), "decimal")
    numbering.set(qn("w:start"), "1")
    composer = Composer(document)
    composer.restart_numbering = False
    index = 0
    for name, block in blocks:
        if name == "cover" and prepare_cover is not None:
            prepare_cover(block)
        before = len(body)
        composer.insert(index, block, remove_property_fields=False)
        index += len(body) - before
        boundary = body[index - 1] if len(body) > before else None
        if boundary is None or boundary.tag != qn("w:p"):
            boundary = OxmlElement("w:p")
            body.insert(index, boundary)
            index += 1
        boundary.get_or_add_pPr()._insert_sectPr(
            _section_properties(document, name, block, composer)
        )

    if header_title:
        for section in document.sections:
            for story in (section.header, section.even_page_header, section.first_page_header):
                for paragraph in story.paragraphs:
                    if paragraph.text.strip() == "页眉示例":
                        paragraph.text = header_title
    composer.renumber_docpr_ids()
    composer.renumber_nvpicpr_ids()
    return index
