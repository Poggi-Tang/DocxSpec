"""Read Word field instructions, including fields split over multiple runs."""

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.oxml import parse_xml
from docx.opc.packuri import PACKAGE_URI, PackURI
from docx.oxml.ns import qn


def document_part_uri(package):
    root = parse_xml(package.read(PACKAGE_URI.rels_uri.membername))
    for relation in root.Relationship_lst:
        if relation.reltype == RT.OFFICE_DOCUMENT and relation.target_mode == "Internal":
            return PackURI.from_rel_ref(PACKAGE_URI, relation.target_ref)
    raise ValueError("DOCX has no internal document part")


def story_parts(package, *, active_only=False):
    """Find reachable Word stories, even if Office or DS assembly relocated them."""
    main = document_part_uri(package)
    yield main.membername, "正文"
    if main.rels_uri.membername not in package.namelist():
        return
    areas = {
        RT.HEADER: "页眉",
        RT.FOOTER: "页脚",
        RT.FOOTNOTES: "脚注",
        RT.ENDNOTES: "尾注",
        RT.COMMENTS: "批注",
    }
    main_xml = parse_xml(package.read(main.membername))
    referenced = {
        reference.get(qn("r:id"))
        for reference in main_xml.iter(qn("w:headerReference"), qn("w:footerReference"))
    }
    relations = parse_xml(package.read(main.rels_uri.membername)).Relationship_lst
    if active_only:
        enabled = False
        for relation in relations:
            if relation.reltype == RT.SETTINGS and relation.target_mode == "Internal":
                name = PackURI.from_rel_ref(main.baseURI, relation.target_ref).membername
                settings = parse_xml(package.read(name))
                enabled = _enabled(settings.find(qn("w:evenAndOddHeaders")))
                break
        referenced = _active_references(main_xml, enabled)
    seen = set()
    for relation in relations:
        if relation.reltype in areas and relation.target_mode == "Internal":
            if relation.reltype in {RT.HEADER, RT.FOOTER} and relation.rId not in referenced:
                continue
            target = PackURI.from_rel_ref(main.baseURI, relation.target_ref).membername
            if target not in seen:
                seen.add(target)
                yield target, areas[relation.reltype]


def _enabled(element):
    return element is not None and element.get(qn("w:val")) not in {"0", "false", "off"}


def _active_references(main_xml, even):
    active = set()
    current = {}
    wanted = {"default", "even"} if even else {"default"}
    types = {qn("w:headerReference"), qn("w:footerReference")}
    for section in main_xml.iter(qn("w:sectPr")):
        if section.getparent().tag not in {qn("w:pPr"), qn("w:body")}:
            continue
        for ref in section:
            if ref.tag in types:
                current[ref.tag, ref.get(qn("w:type"))] = ref.get(qn("r:id"))
        variants = wanted | {"first"} if _enabled(section.find(qn("w:titlePg"))) else wanted
        active.update(rid for (_, variant), rid in current.items() if variant in variants)
    return active


def _read_fields(root, include_results):
    stack = []
    tags = [qn("w:fldSimple"), qn("w:fldChar"), qn("w:instrText")]
    if include_results:
        tags.append(qn("w:t"))
    for node in root.iter(*tags):
        if node.tag == qn("w:fldSimple"):
            text = (
                "".join(child.text or "" for child in node.iter(qn("w:t")))
                if include_results
                else ""
            )
            yield node, node, None, text, any(frame[2] is not None for frame in stack)
        elif node.tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            if kind == "begin":
                stack.append([node, [], None])
            elif kind == "separate" and stack:
                stack[-1][2] = []
            elif kind == "end" and stack:
                owner, runs, result = stack.pop()
                yield (
                    owner,
                    node,
                    runs,
                    "".join(result or ()),
                    any(frame[2] is not None for frame in stack),
                )
        elif node.tag == qn("w:instrText"):
            if stack and stack[-1][2] is None:
                stack[-1][1].append(node)
        else:
            for _, _, result in stack:
                if result is not None:
                    result.append(node.text or "")


def iter_fields(root):
    """Yield the opening node, closing node, and instruction runs of each field."""
    for owner, end, runs, _, _ in _read_fields(root, False):
        yield owner, end, runs


def iter_field_results(root):
    """Yield fields with saved result text, including text from nested TOC entries."""
    for owner, _, runs, text, cached in _read_fields(root, True):
        if not cached:
            yield owner, field_instruction(owner, runs), text


def field_instruction(owner, runs):
    if runs is None:
        return owner.get(qn("w:instr"), "")
    return "".join(node.text or "" for node in runs)
