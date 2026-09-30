"""Semantic equivalence between SREF documents.

Two documents are equivalent when they say the same thing. That is not the same
as being identical bytes, and the specification is explicit about it: property
order carries no meaning (section 4), SREF defines no canonical JSON, and a
member holding its own defined default is equal to that member being absent
(section 24).

This module is the normative home for that comparison. What is deliberately
*not* normalized:

- array order is meaning everywhere it appears, so nothing is sorted;
- unknown standard members and extension members are compared exactly,
  including their JSON types, because a reader may not interpret them and a
  writer may not reshape them;
- numbers are compared as their literal text, so an amount that passed through
  a binary float shows up as the different value it now is rather than being
  rounded back into agreement.
"""

from __future__ import annotations

import json
from typing import Any

#: Members SREF defines as having a default, where an omitted member and an
#: explicit default mean the same thing (section 24). A writer MAY materialize
#: or omit either spelling, so a comparison must accept both.
OMISSIBLE_DEFAULTS = {
    "approximate": False,
    "optional": False,
}


def equivalent(left: Any, right: Any) -> bool:
    """Report whether two documents say the same thing."""
    return canonical(left) == canonical(right)


def canonical(node: Any) -> Any:
    """Reduce a document to its meaning.

    Object members are sorted because their order is not meaning. Array items
    are not, because theirs is. A member holding its defined default is dropped
    so that it compares equal to the same member being absent.
    """
    if isinstance(node, dict):
        return {
            name: canonical(value)
            for name, value in sorted(node.items())
            if OMISSIBLE_DEFAULTS.get(name, _ABSENT) != value
        }
    if isinstance(node, list):
        return [canonical(item) for item in node]
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, (int, float)):
        # Tagged so a number cannot compare equal to a string spelling of itself.
        return ("number", repr(node))
    return node


def difference(left: Any, right: Any, path: str = "") -> str:
    """Describe, by path, the first place two documents stop agreeing."""
    left, right = canonical(left), canonical(right)
    return _difference(left, right, path)


def _difference(left: Any, right: Any, path: str) -> str:
    if isinstance(left, dict) and isinstance(right, dict):
        for name in sorted(set(left) | set(right)):
            where = f"{path}.{name}" if path else name
            if name not in left:
                return f"{where}: added {_render(right[name])}"
            if name not in right:
                return f"{where}: lost {_render(left[name])}"
            if left[name] != right[name]:
                return _difference(left[name], right[name], where)
        return ""
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path}: {len(left)} items became {len(right)}"
        for index, (first, second) in enumerate(zip(left, right)):
            if first != second:
                return _difference(first, second, f"{path}[{index}]")
        return ""
    if left == right:
        return ""
    return f"{path}: {_render(left)} became {_render(right)}"


def _render(value: Any) -> str:
    if isinstance(value, tuple) and len(value) == 2 and value[0] == "number":
        return value[1]
    try:
        return json.dumps(value)[:120]
    except TypeError:  # pragma: no cover - canonical output is JSON-shaped
        return repr(value)[:120]


class _Absent:
    def __eq__(self, other: object) -> bool:
        return False

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<absent>"


_ABSENT = _Absent()
