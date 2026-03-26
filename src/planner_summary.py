"""
Planner-facing metrics for the Streamlit summary table and consistency checks.
"""
from __future__ import annotations

from typing import Any


def width_planning_status(
    panel: dict,
    header: dict,
    planned_mm: float,
    tol_mm: float = 5.0,
) -> str:
    """
    Short Hebrew label for how the entered width relates to computed flat width.
    """
    if panel.get("lock_flat_width_mm"):
        return "נעול"
    w = panel.get("width_mm")
    if w is None or w == "":
        return "אוטומטי"
    try:
        wv = float(w)
    except (TypeError, ValueError):
        return "קלט"
    if planned_mm <= 0:
        return "—"
    if abs(wv - planned_mm) <= tol_mm:
        return "תואם"
    return "בדוק"


def build_planner_summary_rows(
    panels: list[dict[str, Any]],
    header: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], float, int]:
    """
    Rows for the order summary: planned flat width, optional manual input, status, area.

    Returns (rows, total_area_m2, total_quantity).
    """
    from .output import get_width, panel_name

    hdr = dict(header or {})
    rows: list[dict[str, Any]] = []
    total_area = 0.0
    total_qty = 0

    for i, p in enumerate(panels):
        if not isinstance(p, dict):
            continue
        length = float(p.get("length_mm") or 0)
        planned = float(get_width(p, hdr))
        qty = int(p.get("quantity") or 1)
        area = (length * planned * qty) / 1_000_000 if planned else 0.0
        total_area += area
        total_qty += qty

        w_in = p.get("width_mm")
        input_disp = "—"
        if w_in is not None and str(w_in).strip() != "":
            try:
                input_disp = str(int(float(w_in)))
            except (TypeError, ValueError):
                input_disp = str(w_in)

        status = width_planning_status(p, hdr, planned)

        rows.append(
            {
                "#": i + 1,
                "שם": panel_name(p, i),
                "אורך": int(length),
                "רוחב לתכנון": int(round(planned)) if planned else 0,
                "רוחב בקלט": input_disp,
                "מצב": status,
                "כמות": qty,
                'שטח מ"ר': round(area, 2),
            }
        )

    return rows, total_area, total_qty
