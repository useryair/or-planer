"""
Validate extracted order JSON schema before processing.
"""
from collections import Counter


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
        header = header if isinstance(header, dict) else {}
        from .output import get_width

        for i, panel in enumerate(panels):
            if not isinstance(panel, dict):
                errors.append(f"פנל {i + 1}: חייב להיות אובייקט")
                continue
            errs_at_panel_start = len(errors)
            # Required: length_mm, quantity
            if panel.get("length_mm") is None:
                errors.append(f"פנל {i + 1}: חסר אורך (length_mm)")
            if panel.get("quantity") is None:
                errors.append(f"פנל {i + 1}: חסר כמות (quantity)")

            length_val: float | None = None
            if panel.get("length_mm") is not None:
                try:
                    length_val = float(panel.get("length_mm"))
                except (TypeError, ValueError):
                    errors.append(f"פנל {i + 1}: אורך (length_mm) חייב להיות מספר")
                else:
                    if length_val <= 0:
                        errors.append(
                            f"פנל {i + 1}: אורך חייב להיות חיובי (מ״מ) — אחרת שטח והזמנה שגויים."
                        )

            if panel.get("quantity") is not None:
                try:
                    qf = float(panel.get("quantity"))
                    qi = int(qf)
                except (TypeError, ValueError):
                    errors.append(f"פנל {i + 1}: כמות (quantity) חייבת להיות מספר")
                else:
                    if qi < 1:
                        errors.append(
                            f"פנל {i + 1}: כמות חייבת להיות לפחות 1 — כמות 0 או שלילית שוברת סיכומים."
                        )
                    elif abs(qf - qi) > 1e-6:
                        errors.append(
                            f"פנל {i + 1}: כמות חייבת להיות מספר שלם (לא {panel.get('quantity')})."
                        )

            pdim = panel.get("profile_dimensions")
            if pdim is not None:
                if not isinstance(pdim, list):
                    errors.append(f"פנל {i + 1}: profile_dimensions חייב להיות מערך מספרים")
                elif len(pdim) == 0:
                    errors.append(f"פנל {i + 1}: profile_dimensions ריק — השתמש ב-null אם אין חתך")
                else:
                    for j, x in enumerate(pdim):
                        if x is None or x == "":
                            errors.append(f"פנל {i + 1}: ערך חסר בפרופיל (מקום {j + 1})")
                            break
                        try:
                            float(x)
                        except (TypeError, ValueError):
                            errors.append(
                                f"פנל {i + 1}: ערך לא מספרי בפרופיל (מקום {j + 1})"
                            )
                            break

            # Financial: no usable flat width → area and CNC layout are wrong
            if (
                length_val is not None
                and length_val > 0
                and len(errors) == errs_at_panel_start
            ):
                try:
                    w_eff = float(get_width(panel, header))
                except Exception:
                    w_eff = 0.0
                if w_eff <= 0:
                    pid = str(panel.get("panel_id") or "").strip() or f"שורה {i + 1}"
                    errors.append(
                        f"פנל {i + 1} ({pid}): אין רוחב פריסה שטוח — מלא "
                        f'ממדי פרופיל או עמודת «רוחב», או בדוק מצב פריסה (מפותח/ישן). בלי זה השטח יוצא 0.'
                    )

    return len(errors) == 0, errors


def validate_and_raise(data: dict) -> None:
    """Validate data and raise ValueError with Hebrew message if invalid."""
    valid, errors = validate_order_data(data)
    if not valid:
        msg = "שגיאות באימות נתונים:\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)


def _dims_tuple(panel: dict) -> tuple[float, ...] | None:
    from .flat_pattern import effective_profile_segments

    d = effective_profile_segments(panel)
    if not d:
        return None
    try:
        return tuple(round(float(x), 3) for x in d)
    except (TypeError, ValueError):
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

    missing_id_rows = [
        i + 1
        for i, panel in enumerate(panels)
        if isinstance(panel, dict) and not str(panel.get("panel_id") or "").strip()
    ]
    if missing_id_rows:
        tail = ", ".join(str(n) for n in missing_id_rows[:12])
        if len(missing_id_rows) > 12:
            tail += ", …"
        warnings.append(
            f"שורות ללא מק״ט ({len(missing_id_rows)}): {tail} — מומלץ למלא לזיהוי ושמות קבצים."
        )

    by_id: dict[str, list[tuple[float, ...] | None]] = {}
    id_counts: Counter[str] = Counter()
    for i, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        raw_id = panel.get("panel_id")
        pid = str(raw_id).strip() if raw_id is not None else ""
        if pid:
            id_counts[pid] += 1
        if not pid:
            continue
        dt = _dims_tuple(panel)
        by_id.setdefault(pid, []).append(dt)

    dup_ids = [(p, c) for p, c in id_counts.items() if c >= 2]
    if dup_ids:
        parts = [f'"{p}" ({c})' for p, c in sorted(dup_ids, key=lambda x: (-x[1], x[0]))]
        warnings.append(
            "מק״ט חוזר בשורות מרובות: "
            + ", ".join(parts)
            + " — תקין אם אותו פריט בכמה שורות; אחרת בדוק כפילות."
        )

    for pid, dim_list in by_id.items():
        non_null = [d for d in dim_list if d is not None]
        if len(non_null) >= 2 and len(set(non_null)) > 1:
            warnings.append(
                f'אותו מק״ט "{pid}" מופיע עם ממדי פרופיל שונים — בדוק שיוך שורה↔חתך.'
            )

    header = data.get("header") if isinstance(data.get("header"), dict) else {}
    from .flat_pattern import legacy_horizontal_width_mm
    from .output import get_width

    length_suspect_mm = 25_000.0

    width_tol_mm = 5.0
    mode = str(header.get("flat_pattern_mode") or "developed").strip().lower()
    for i, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        try:
            ln = float(panel.get("length_mm") or 0)
        except (TypeError, ValueError):
            ln = 0.0
        if ln >= length_suspect_mm:
            warnings.append(
                f"פנל {i + 1}: אורך {ln:.0f} מ\"מ — חריג; אם זו טעות חילוץ, השטח וההזמנה יצאו מנופחים."
            )
        if panel.get("lock_flat_width_mm"):
            continue
        w = panel.get("width_mm")
        if w is None:
            continue
        try:
            wv = float(w)
        except (TypeError, ValueError):
            continue
        comp = get_width(panel, header)
        if comp <= 0:
            continue
        if abs(wv - comp) > width_tol_mm:
            hint = ""
            if mode == "developed":
                leg = legacy_horizontal_width_mm(panel)
                if leg is not None and abs(wv - leg) <= width_tol_mm:
                    hint = (
                        " הערך תואם כמעט רק **סכום קטעים אופקיים**; בפריסה מפותחת נכללים כל הקטעים + כיפוף."
                    )
            warnings.append(
                f"פנל {i + 1}: רוחב מוזן {wv:.0f} מ\"מ לעומת פריסה מחושבת ~{comp:.0f} מ\"מ "
                f'(חתך + עובי + כיפוף במצב "{mode}"). רוקן את «רוחב» לחישוב אוטומטי או עדכן למספר נכון.{hint}'
            )

    return warnings
