"""
Validate extracted order JSON schema before processing.
"""
from typing import Any


def validate_order_data(data: dict) -> tuple[bool, list[str]]:
    """
    Validate order data structure. Returns (is_valid, list of error messages).
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["נתונים חייבים להיות אובייקט JSON"]

    # Header
    header = data.get("header")
    if header is None:
        errors.append("חסר שדה header")
    elif not isinstance(header, dict):
        errors.append("header חייב להיות אובייקט")
    else:
        # Optional header fields - no strict requirement
        pass

    # Panels
    panels = data.get("panels")
    if panels is None:
        errors.append("חסר שדה panels")
    elif not isinstance(panels, list):
        errors.append("panels חייב להיות מערך")
    else:
        for i, panel in enumerate(panels):
            if not isinstance(panel, dict):
                errors.append(f"פנל {i + 1}: חייב להיות אובייקט")
                continue
            # Required: length_mm, quantity
            if panel.get("length_mm") is None:
                errors.append(f"פנל {i + 1}: חסר אורך (length_mm)")
            if panel.get("quantity") is None:
                errors.append(f"פנל {i + 1}: חסר כמות (quantity)")

    return len(errors) == 0, errors


def validate_and_raise(data: dict) -> None:
    """Validate data and raise ValueError with Hebrew message if invalid."""
    valid, errors = validate_order_data(data)
    if not valid:
        msg = "שגיאות באימות נתונים:\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)
