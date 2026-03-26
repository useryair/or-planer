"""
Flat-pattern (plane) span for cross-section profiles: thickness + bend allowance.

Convention (default basis=mold):
  Segments in profile_dimensions are straight mold-line / tangent lengths along the path.
  Each bend adds neutral-axis arc length BA = θ_rad * (R_inner + K*T).

Optional basis=outside: outside-tangent lengths; per bend we apply bend-style deduction.

legacy: previous app behavior — only sum of horizontal (even-index) segments (projection).

Geometry uses **only** the numbers in `profile_dimensions` (written order). No segment is inferred
from `bend_offset_mm`; include every leg (e.g. bottom return) in the comma list when it exists on the drawing.
"""
from __future__ import annotations

import math
from typing import Any


def effective_profile_segments(panel: dict) -> list[float] | None:
    """
    Parsed segment list from profile_dimensions only (same as written on the order / drawing).

    Used for developed length, DXF/PDF polylines, and bend count.
    """
    dims = panel.get("profile_dimensions")
    if not isinstance(dims, list) or len(dims) < 2:
        return None
    try:
        return [float(x) for x in dims]
    except (TypeError, ValueError):
        return None


def _hdr_float(header: dict, key: str, default: float) -> float:
    v = header.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def bend_allowance_mm(
    angle_deg: float,
    thickness_mm: float,
    inside_radius_mm: float,
    k_factor: float,
) -> float:
    """Arc length along neutral axis for one bend (mm)."""
    theta = math.radians(float(angle_deg))
    r_n = float(inside_radius_mm) + float(k_factor) * float(thickness_mm)
    return theta * r_n


def profile_bend_count(segment_count: int) -> int:
    """Open orthogonal chain: one bend between each pair of consecutive segments."""
    if segment_count < 2:
        return 0
    return segment_count - 1


def developed_profile_girth_mm(panel: dict, header: dict) -> float | None:
    """
    Developed length along the full cross-section path (mm), including bend allowance.
    Returns None if no usable profile_dimensions.
    """
    segs = effective_profile_segments(panel)
    if segs is None:
        return None

    thick = _hdr_float(header, "thickness_mm", 2.0)
    r_override = panel.get("bend_radius_mm")
    if r_override is not None and str(r_override).strip() != "":
        try:
            r_in = float(r_override)
        except (TypeError, ValueError):
            r_in = max(thick * 1.5, 1.0)
    else:
        dr = header.get("default_bend_radius_mm")
        if dr is not None and str(dr).strip() != "":
            try:
                r_in = float(dr)
            except (TypeError, ValueError):
                r_in = max(thick * 1.5, 1.0)
        else:
            r_in = max(thick * 1.5, 1.0)
    pk = panel.get("k_factor")
    k = float(pk) if pk is not None and str(pk).strip() != "" else _hdr_float(header, "k_factor", 0.4)
    pba = panel.get("bend_allowance_angle_deg")
    brake_deg = (
        float(pba)
        if pba is not None and str(pba).strip() != ""
        else _hdr_float(header, "bend_allowance_angle_deg", 90.0)
    )
    n = profile_bend_count(len(segs))
    ba = bend_allowance_mm(brake_deg, thick, r_in, k)
    raw = sum(segs)

    basis = (header.get("flat_pattern_dimension_basis") or "mold").strip().lower()
    if basis == "legacy":
        return float(sum(segs[i] for i in range(0, len(segs), 2)))
    if basis == "outside":
        half = math.radians(brake_deg / 2.0)
        bd = 2.0 * (r_in + thick) * math.tan(half) - ba
        return raw - n * bd
    # mold (default): mold-line straights + arc at each bend
    return raw + n * ba


def legacy_horizontal_width_mm(panel: dict) -> float | None:
    segs = effective_profile_segments(panel)
    if not segs:
        return None
    try:
        return float(sum(float(segs[i]) for i in range(0, len(segs), 2)))
    except (TypeError, ValueError, IndexError):
        return None


def get_flat_width_mm(panel: dict, header: dict | None = None) -> float:
    """
    Width used for flat sheet (plane) — area, red rectangle, DXF flat layout.

    Priority:
      1. width_mm if lock_flat_width_mm is true (manual override).
      2. Developed girth from profile when flat_pattern_mode != 'legacy' and profile exists.
      3. Explicit width_mm.
      4. Legacy: sum of horizontal segments only.
      5. 0
    """
    hdr: dict[str, Any] = header if isinstance(header, dict) else {}
    mode = (hdr.get("flat_pattern_mode") or "developed").strip().lower()

    w_raw = panel.get("width_mm")
    locked = bool(panel.get("lock_flat_width_mm"))
    if locked and w_raw is not None:
        try:
            return float(w_raw)
        except (TypeError, ValueError):
            pass

    if mode != "legacy":
        g = developed_profile_girth_mm(panel, hdr)
        if g is not None:
            return g

    if w_raw is not None:
        try:
            return float(w_raw)
        except (TypeError, ValueError):
            pass

    leg = legacy_horizontal_width_mm(panel)
    if leg is not None:
        return leg
    return 0.0
