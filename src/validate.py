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


def _dims_tuple(panel: dict) -> tuple[float, ...] | None:
    d = panel.get("profile_dimensions")
    if not isinstance(d, list) or not d:
        return None
    try:
        return tuple(round(float(x), 3) for x in d)
    except (TypeError, ValueError):
        return None


def _sum_horizontal_segments(panel: dict) -> float | None:
    d = panel.get("profile_dimensions")
    if not isinstance(d, list) or not d:
        return None
    try:
        return float(sum(float(d[i]) for i in range(0, len(d), 2)))
    except (TypeError, ValueError, IndexError):
        return None


def validate_order_warnings(data: dict) -> list[str]:
    """
    Non-blocking consistency hints (Hebrew). Does not replace validate_order_data.
    """
    warnings: list[str] = []
    if not isinstance(data, dict):
        return warnings
    panels = data.get("panels")
    if not isinstance(panels, list):
        return warnings

    by_id: dict[str, list[tuple[float, ...] | None]] = {}
    for i, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        raw_id = panel.get("panel_id")
        pid = str(raw_id).strip() if raw_id is not None else ""
        if not pid:
            continue
        dt = _dims_tuple(panel)
        by_id.setdefault(pid, []).append(dt)

    for pid, dim_list in by_id.items():
        non_null = [d for d in dim_list if d is not None]
        if len(non_null) >= 2 and len(set(non_null)) > 1:
            warnings.append(
                f'אותו מק״ט "{pid}" מופיע עם ממדי פרופיל שונים — בדוק שיוך שורה↔חתך.'
            )

    width_tol_mm = 5.0
    for i, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        w = panel.get("width_mm")
        if w is None:
            continue
        try:
            wv = float(w)
        except (TypeError, ValueError):
            continue
        sh = _sum_horizontal_segments(panel)
        if sh is None or sh <= 0:
            continue
        if abs(wv - sh) > width_tol_mm:
            warnings.append(
                f"פנל {i + 1}: רוחב {wv:.0f} מ\"מ שונה מסכום קטעי החתך האופקיים (~{sh:.0f}). "
                "אם הרוחב נכון — עדכן את עמודת הפרופיל; אם הפרופיל נכון — תקן רוחב."
            )

    return warnings
