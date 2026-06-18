"""Brand-casing helpers for user-facing strings.

Some product names are intentionally styled lower-case (e.g. ``groundcover``).
Generic humanizers that ``.title()`` an identifier would capitalize them, so
apply :func:`apply_brand_casing` after title-casing to restore brand styling.
"""

from __future__ import annotations

import re

# Map of canonical lowercase brand term -> rendered casing.
_BRAND_CASING: dict[str, str] = {
    "groundcover": "groundcover",
}

_BRAND_RE = re.compile(
    "|".join(re.escape(term) for term in _BRAND_CASING),
    re.IGNORECASE,
)


def apply_brand_casing(text: str) -> str:
    """Rewrite any brand term in ``text`` to its canonical styling."""
    if not text:
        return text
    return _BRAND_RE.sub(lambda m: _BRAND_CASING[m.group(0).lower()], text)
