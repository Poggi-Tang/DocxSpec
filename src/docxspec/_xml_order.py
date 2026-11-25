"""Place OOXML children in schema order while preserving unrelated elements."""

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def place_before(parent, child, successors):
    """Insert or move a child before the first actual successor in the parent."""
    tags = {qn(tag) for tag in successors}
    for sibling in parent:
        if sibling is child:
            return
        if sibling.tag in tags:
            sibling.addprevious(child)
            return
    parent.append(child)


def child_in_order(parent, tag, successors):
    child = parent.find(qn(tag))
    if child is None:
        child = OxmlElement(tag)
    place_before(parent, child, successors)
    return child
