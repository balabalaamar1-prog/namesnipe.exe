"""Discord username rules + input parsing.

Discord (new username system): 2-32 chars, lowercase letters, digits,
underscore and period; no two periods in a row.
"""
import re
from typing import List, Optional

_ALLOWED = re.compile(r"^[a-z0-9_.]+$")


def normalize(name: str) -> str:
    return name.strip().lstrip("@").lower()


def validate(name: str) -> Optional[str]:
    """Return an error message, or None if the name is valid."""
    if not name:
        return "empty"
    if len(name) < 2:
        return "too short (min 2)"
    if len(name) > 32:
        return "too long (max 32)"
    if not _ALLOWED.match(name):
        return "only a-z, 0-9, _ and . allowed"
    if ".." in name:
        return "no two periods in a row"
    return None


def parse_names(text: str) -> List[str]:
    """Split on newlines / commas / spaces / semicolons, normalise, de-duplicate."""
    seen, out = set(), []
    for token in re.split(r"[\s,;]+", text):
        n = normalize(token)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
