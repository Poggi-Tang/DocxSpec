"""Read Word field instructions, including fields split over multiple runs."""

from docx.oxml.ns import qn


def iter_fields(root):
    """Yield the opening node, closing node, and instruction runs of each field."""
    stack = []
    for node in root.iter(qn("w:fldSimple"), qn("w:fldChar"), qn("w:instrText")):
        if node.tag == qn("w:fldSimple"):
            yield node, node, None
        elif node.tag == qn("w:fldChar"):
            kind = node.get(qn("w:fldCharType"))
            if kind == "begin":
                stack.append([node, [], False])
            elif kind == "separate" and stack:
                stack[-1][2] = True
            elif kind == "end" and stack:
                owner, runs, _ = stack.pop()
                yield owner, node, runs
        elif stack and not stack[-1][2]:
            stack[-1][1].append(node)


def field_instruction(owner, runs):
    if runs is None:
        return owner.get(qn("w:instr"), "")
    return "".join(node.text or "" for node in runs)
