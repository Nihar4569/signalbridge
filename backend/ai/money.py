"""Turn paise into finished rupee strings before data reaches Gemini.

Models get the divide-by-100 step wrong (we saw Rs 50,000 reported as
Rs 50,00,000), so money is formatted here, deterministically, and the model
only has to quote it.
"""
from __future__ import annotations


def rupees_text(minor: int | float) -> str:
    """11300000 paise -> 'Rs 1,13,000' (Indian digit grouping)."""
    rupees = round(minor / 100)
    digits = str(abs(rupees))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return ("-" if rupees < 0 else "") + "Rs " + digits


def humanize_money(value):
    """Recursively rename `*_minor` numeric fields to `*_rupees` formatted strings."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(key, str) and key.endswith("_minor") and isinstance(item, (int, float)) and not isinstance(item, bool):
                out[key[: -len("_minor")] + "_rupees"] = rupees_text(item)
            else:
                out[key] = humanize_money(item)
        return out
    if isinstance(value, list):
        return [humanize_money(item) for item in value]
    return value
