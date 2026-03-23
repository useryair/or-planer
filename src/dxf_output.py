"""
Generate DXF files for each panel - flat profile for CNC cutting.
Also create PDF copies of each DXF for viewing/printing.

Fixes:
  - Width derived from horizontal dimension segments (not max)
  - Proper DXF layer colors + lineweights
  - Dimension annotations on DXF
  - Better PDF scale + dimension labels
"""
import zipfile
from pathlib import Path

import ezdxf
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .output import get_width, panel_name, _register_hebrew_font, _visual


def profile_points_from_dimensions(dims: list[float]) -> list[tuple[float, float]]:
    """
    Build polyline points from profile_dimensions.
    Alternating segments: horizontal (right), vertical (down), ...
    e.g. [25, 20, 170, 20, 25] → U-shape cross section
    """
    if not dims:
        return [(0.0, 0.0)]
    points = [(0.0, 0.0)]
    x, y = 0.0, 0.0
    for i, d in enumerate(dims):
        val = float(d)
        if i % 2 == 0:   # horizontal
            x += val
        else:             # vertical (down)
            y -= val
        points.append((x, y))
    return points


def _setup_dim_style(doc) -> str:
    """Create a clean dimension style with filled arrows."""
    style_name = "OR_DIM"
    dim_style = doc.dimstyles.new(style_name)
    dim_style.dxf.dimtxt = 3.5       # text height
    dim_style.dxf.dimasz = 3.0       # arrow size
    dim_style.dxf.dimexe = 1.5       # extension line beyond dim line
    dim_style.dxf.dimexo = 1.5       # extension line offset from origin
    dim_style.dxf.dimgap = 1.0       # gap around text
    dim_style.dxf.dimclrd = 3        # dim line color (green)
    dim_style.dxf.dimclre = 3        # extension line color (green)
    dim_style.dxf.dimclrt = 3        # text color (green)
    dim_style.dxf.dimdec = 0         # no decimals
    dim_style.dxf.dimblk = ezdxf.ARROWS.closed_filled
    return style_name


def _dxf_add_dim(msp, p1, p2, base, dim_style, angle=0, txt=3.0, asz=2.5):
    """Add a linear dimension and render it."""
    msp.add_linear_dim(
        base=base, p1=p1, p2=p2, angle=angle,
        dimstyle=dim_style,
        override={"dimtad": 1, "dimtxt": txt, "dimasz": asz},
        dxfattribs={"layer": "DIMS"},
    ).render()


def _dxf_draw_profile(msp, points, dims, ox, oy, scale, dim_style):
    """Draw profile cross-section at offset (ox, oy) with given scale, plus dimensions."""
    def t(x, y):
        return (ox + x * scale, oy - y * scale)

    sheet_pts = [t(*p) for p in points]
    msp.add_lwpolyline(sheet_pts, dxfattribs={"layer": "PROFILE", "lineweight": 50})

    px, py = 0.0, 0.0
    for i, d in enumerate(dims):
        val = float(d)
        if i % 2 == 0:
            p1, p2 = t(px, py), t(px + val, py)
            if val * scale > 10:
                _dxf_add_dim(msp, p1, p2, ((p1[0]+p2[0])/2, p1[1] + 6), dim_style, txt=2.5, asz=2)
            px += val
        else:
            p1, p2 = t(px, py), t(px, py - val)
            if val * scale > 10:
                _dxf_add_dim(msp, p1, p2, (p1[0] + 6, (p1[1]+p2[1])/2), dim_style, angle=90, txt=2.5, asz=2)
            py -= val

    # Total width below
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    sp1, sp2 = t(min(xs), max(abs(y) for y in ys)), t(max(xs), max(abs(y) for y in ys))
    sp1 = t(0, min(ys))
    sp2 = t(max(xs), min(ys))
    _dxf_add_dim(msp, sp1, sp2, ((sp1[0]+sp2[0])/2, sp1[1] - 10), dim_style, txt=3.5, asz=3)


def _dxf_draw_bent_view(msp, dims, cx, cy, avail_h, dim_style):
    """Draw bent/side elevation view centered at (cx, cy)."""
    if not dims or len(dims) < 3:
        return

    vert_vals = [float(dims[i]) for i in range(1, len(dims), 2)]
    total_h = sum(vert_vals) or 1
    top_flange = float(dims[0])
    bot_flange = float(dims[-1]) if len(dims) % 2 == 1 else 0

    s = avail_h * 0.6 / total_h
    bx = cx - max(top_flange, bot_flange) * s / 2
    by = cy - total_h * s / 2

    pts = [(bx + top_flange * s, by + total_h * s), (bx, by + total_h * s)]
    cur_y = by + total_h * s
    for vi, vv in enumerate(vert_vals):
        cur_y -= vv * s
        pts.append((bx, cur_y))
    if bot_flange > 0:
        pts.append((bx + bot_flange * s, by))
    msp.add_lwpolyline(pts, dxfattribs={"layer": "PROFILE", "lineweight": 50})

    right_x = bx + max(top_flange, bot_flange) * s
    _dxf_add_dim(msp, (right_x, by), (right_x, by + total_h * s),
                 (right_x + 8, cy), dim_style, angle=90, txt=3, asz=2.5)
    if top_flange > 0:
        _dxf_add_dim(msp, (bx, by + total_h * s), (bx + top_flange * s, by + total_h * s),
                     (bx + top_flange * s / 2, by + total_h * s + 6), dim_style, txt=2.5, asz=2)


def _dxf_draw_fallback_bent_view(msp, cx, cy, avail_h, dim_style, bend_angle_deg: float = 93) -> None:
    """L-shaped side schematic when profile_dimensions are missing or too short."""
    target = max(50.0, min(90.0, (avail_h - 25) * 0.35))
    V = H = target
    bx = cx - H / 2
    by = cy - V / 2
    pts = [(bx + H, by + V), (bx, by + V), (bx, by), (bx + H, by)]
    msp.add_lwpolyline(pts, dxfattribs={"layer": "PROFILE", "lineweight": 50})
    _dxf_add_dim(
        msp, (bx, by), (bx, by + V), (bx - 14, by + V / 2), dim_style, angle=90, txt=2.5, asz=2,
    )
    _dxf_add_dim(
        msp, (bx, by), (bx + H, by), (bx + H / 2, by - 10), dim_style, txt=2.5, asz=2,
    )
    ang = int(bend_angle_deg) if bend_angle_deg else 93
    msp.add_text(f"{ang} deg", dxfattribs={"height": 3, "layer": "TEXT"}).set_placement(
        (bx + H * 0.35, by + V * 0.55), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
    )


def _dxf_draw_flat_layout(msp, cx, cy, length, width, avail_w, avail_h, dim_style):
    """Draw flat layout rectangle with dashed lines and dimensions."""
    if length <= 0 or width <= 0:
        return
    s = min((avail_w - 30) / length, (avail_h - 30) / width) * 0.75
    rw, rh = length * s, width * s
    rx, ry = cx - rw / 2, cy - rh / 2

    msp.add_lwpolyline([
        (rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh)
    ], close=True, dxfattribs={"layer": "FLAT_LAYOUT", "lineweight": 25, "linetype": "DASHED"})

    _dxf_add_dim(msp, (rx, ry), (rx + rw, ry),
                 (cx, ry - 10), dim_style, txt=3, asz=2.5)
    _dxf_add_dim(msp, (rx + rw, ry), (rx + rw, ry + rh),
                 (rx + rw + 10, cy), dim_style, angle=90, txt=3, asz=2.5)

    msp.add_text("Flat Layout", dxfattribs={"height": 3.5, "layer": "TEXT"}).set_placement(
        (cx, ry + rh + 5), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def _dxf_draw_table(msp, tx, ty, tw, th, panel, index, header, length, width, area):
    """Draw data table with grid and text."""
    name = panel_name(panel, index)
    qty = int(panel.get("quantity") or 1)
    thick = header.get("thickness_mm") or 2
    ral = header.get("color_ral") or "9011"

    num_cols, num_rows = 8, 3
    cw, rh = tw / num_cols, th / num_rows

    for r in range(num_rows + 1):
        y = ty + r * rh
        lw = 35 if r in (0, num_rows) else 13
        msp.add_line((tx, y), (tx + tw, y), dxfattribs={"layer": "TABLE", "lineweight": lw})
    for c in range(num_cols + 1):
        x = tx + c * cw
        lw = 35 if c in (0, num_cols) else 13
        msp.add_line((x, ty), (x, ty + th), dxfattribs={"layer": "TABLE", "lineweight": lw})

    def cell_text(col, row, text, height=2.5):
        cx = tx + (num_cols - 1 - col) * cw + cw / 2
        cy_t = ty + row * rh + rh / 2
        msp.add_text(str(text), dxfattribs={"height": height, "layer": "TEXT"}).set_placement(
            (cx, cy_t), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    headers = ["Notes", "Area m2", "Qty", "Color", "Thick mm", "Width mm", "Length mm", "Profile"]
    for i, h in enumerate(headers):
        cell_text(i, 2, h, 2.2)

    values = [
        panel.get("notes") or "", f"{area:.4f}", str(qty), f"RAL {ral}",
        str(thick), str(int(width)) if width else "-",
        str(int(length)), f"{name} x{qty}",
    ]
    for i, v in enumerate(values):
        cell_text(i, 1, v, 2.8)

    proj_id = header.get("project_id") or ""
    proj_name = header.get("project_name") or ""
    date = header.get("date") or ""
    mat = header.get("material") or "Aluminum"
    info = {0: mat, 4: f"Date: {date}", 6: f"Project: {proj_id}", 7: proj_name}
    for col, txt in info.items():
        if txt:
            cell_text(col, 0, txt, 2.0)


def create_panel_dxf(panel: dict, index: int, header: dict, output_path: Path) -> None:
    """Create professional DXF drawing sheet: border, 3 views, data table."""
    length = float(panel.get("length_mm") or 0)
    width = get_width(panel)
    dims = panel.get("profile_dimensions")
    name = panel_name(panel, index)
    thick = float(header.get("thickness_mm") or 2)
    qty = int(panel.get("quantity") or 1)
    area = (length * width * qty) / 1_000_000 if width else 0

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()

    doc.layers.add("BORDER",      color=7, lineweight=70)
    doc.layers.add("PROFILE",     color=7, lineweight=50)
    doc.layers.add("DIMS",        color=3, lineweight=13)
    doc.layers.add("TEXT",        color=2, lineweight=13)
    doc.layers.add("FLAT_LAYOUT", color=1, lineweight=25)
    doc.layers.add("TABLE",       color=7, lineweight=25)
    doc.layers.add("CENTERLINE",  color=1, lineweight=13)

    dim_style = _setup_dim_style(doc)

    # A3 landscape (420 x 297 mm)
    PW, PH = 420, 297
    M = 10

    # Border frame
    msp.add_lwpolyline([
        (M, M), (PW - M, M), (PW - M, PH - M), (M, PH - M)
    ], close=True, dxfattribs={"layer": "BORDER", "lineweight": 70})

    # Table zone (bottom 50mm)
    TABLE_H = 45
    table_top = M + TABLE_H
    msp.add_line((M, table_top), (PW - M, table_top),
                 dxfattribs={"layer": "BORDER", "lineweight": 35})

    draw_bot = table_top + 8
    draw_top = PH - M - 5
    draw_h = draw_top - draw_bot
    draw_mid_y = (draw_bot + draw_top) / 2

    third_w = (PW - 2 * M) / 3
    zone1_cx = M + third_w * 0.5
    zone2_cx = M + third_w * 1.5
    zone3_cx = M + third_w * 2.5

    # ── VIEW 1: Profile cross-section (left) ──
    if dims and len(dims) >= 2:
        points = profile_points_from_dimensions(dims)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        rx = max(xs) - min(xs) or 1
        ry = max(ys) - min(ys) or 1
        avail_w = third_w - 35
        avail_h = draw_h - 50
        scale = min(avail_w / rx, avail_h / ry) * 0.7

        ox = zone1_cx - (rx * scale) / 2 - min(xs) * scale
        oy = draw_mid_y + 15 + (ry * scale) / 2 + min(ys) * scale

        _dxf_draw_profile(msp, points, dims, ox, oy, scale, dim_style)

        msp.add_text("B-B (1:5)", dxfattribs={"height": 4, "layer": "TEXT"}).set_placement(
            (zone1_cx, draw_bot + 3), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    elif width > 0:
        # Rectangular fallback
        rect = [(0, 0), (length, 0), (length, width), (0, width)]
        avail_w = third_w - 35
        avail_h = draw_h - 50
        scale = min(avail_w / length, avail_h / width) * 0.65
        ox = zone1_cx - (length * scale) / 2
        oy = draw_mid_y + 15 + (width * scale) / 2
        sheet_pts = [(ox + x * scale, oy - y * scale) for x, y in rect]
        msp.add_lwpolyline(sheet_pts, close=True,
                           dxfattribs={"layer": "PROFILE", "lineweight": 50})
        p1 = sheet_pts[0]
        p2 = sheet_pts[1]
        _dxf_add_dim(msp, p1, p2, ((p1[0]+p2[0])/2, p1[1] - 10), dim_style)
        p3 = sheet_pts[2]
        _dxf_add_dim(msp, p2, p3, (p2[0] + 10, (p2[1]+p3[1])/2), dim_style, angle=90)

    # ── VIEW 2: Bent side view (center) ──
    bend_deg = float(panel.get("bend_angle_deg") or 93)
    if dims and len(dims) >= 3:
        _dxf_draw_bent_view(msp, dims, zone2_cx, draw_mid_y + 15, draw_h - 40, dim_style)
        msp.add_text("Side View", dxfattribs={"height": 3.5, "layer": "TEXT"}).set_placement(
            (zone2_cx, draw_bot + 3), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    else:
        _dxf_draw_fallback_bent_view(msp, zone2_cx, draw_mid_y + 15, draw_h - 40, dim_style, bend_deg)
        msp.add_text("Side View (schematic)", dxfattribs={"height": 3.5, "layer": "TEXT"}).set_placement(
            (zone2_cx, draw_bot + 3), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # ── VIEW 3: Flat layout rectangle (right) ──
    _dxf_draw_flat_layout(msp, zone3_cx, draw_mid_y + 15, length, width,
                          third_w, draw_h - 30, dim_style)

    # ── DATA TABLE (bottom) ──
    _dxf_draw_table(msp, M + 5, M + 3, PW - 2 * M - 10, TABLE_H - 8,
                    panel, index, header, length, width, area)

    doc.saveas(output_path)


# ── PDF panel sheets ──────────────────────────────────────────────────────────

from reportlab.lib import colors as rl_colors


def _dim_arrow(c, x1, y1, x2, y2, size=2.5):
    """Draw a small filled arrow head at (x2,y2) pointing from (x1,y1)."""
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    c.beginPath()
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ux * size + px * size * 0.4, y2 - uy * size + py * size * 0.4)
    p.lineTo(x2 - ux * size - px * size * 0.4, y2 - uy * size - py * size * 0.4)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _draw_dim_h(c, x1, x2, y, label, font_name, offset=12, font_size=6):
    """Draw horizontal dimension line with extension lines and arrows."""
    c.saveState()
    c.setStrokeColorRGB(0.2, 0.2, 0.8)
    c.setFillColorRGB(0.2, 0.2, 0.8)
    c.setLineWidth(0.4)
    ey = y - offset
    c.line(x1, y - 2, x1, ey - 3)
    c.line(x2, y - 2, x2, ey - 3)
    c.line(x1, ey, x2, ey)
    _dim_arrow(c, x2, ey, x1, ey, 2.5)
    _dim_arrow(c, x1, ey, x2, ey, 2.5)
    c.setFont(font_name, font_size)
    mid = (x1 + x2) / 2
    c.drawCentredString(mid, ey + 2, str(label))
    c.restoreState()


def _draw_dim_v(c, x, y1, y2, label, font_name, offset=12, font_size=6):
    """Draw vertical dimension line with extension lines and arrows."""
    c.saveState()
    c.setStrokeColorRGB(0.2, 0.2, 0.8)
    c.setFillColorRGB(0.2, 0.2, 0.8)
    c.setLineWidth(0.4)
    ex = x + offset
    c.line(x + 2, y1, ex + 3, y1)
    c.line(x + 2, y2, ex + 3, y2)
    c.line(ex, y1, ex, y2)
    _dim_arrow(c, ex, y2, ex, y1, 2.5)
    _dim_arrow(c, ex, y1, ex, y2, 2.5)
    c.setFont(font_name, font_size)
    c.saveState()
    c.translate(ex + 3, (y1 + y2) / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, str(label))
    c.restoreState()
    c.restoreState()


def _draw_profile_view(c, cx, cy, avail_w, avail_h, dims, font_name):
    """Draw profile cross-section centered in the given area with dimension lines."""
    if not dims or len(dims) < 2:
        return
    points = profile_points_from_dimensions(dims)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    rx = max(xs) - min(xs) or 1
    ry = max(ys) - min(ys) or 1

    dim_margin = 25
    scale = min((avail_w - dim_margin * 2) / rx, (avail_h - dim_margin * 2) / ry) * 0.85
    ox = cx - (rx * scale) / 2 - min(xs) * scale
    oy = cy + (ry * scale) / 2 + min(ys) * scale

    def to_page(x, y):
        return ox + x * scale, oy - y * scale

    c.saveState()
    c.setLineWidth(1.8)
    c.setStrokeColorRGB(0, 0, 0)
    path = c.beginPath()
    px0, py0 = to_page(*points[0])
    path.moveTo(px0, py0)
    for pt in points[1:]:
        path.lineTo(*to_page(*pt))
    c.drawPath(path, fill=0, stroke=1)

    # Dimension labels on each segment
    px_d, py_d = 0.0, 0.0
    for i, d in enumerate(dims):
        val = float(d)
        if i % 2 == 0:
            sx, sy = to_page(px_d, py_d)
            ex, ey = to_page(px_d + val, py_d)
            if val * scale > 15:
                _draw_dim_h(c, sx, ex, sy, int(val), font_name, offset=10, font_size=5.5)
            px_d += val
        else:
            sx, sy = to_page(px_d, py_d)
            ex, ey = to_page(px_d, py_d - val)
            if val * scale > 15:
                _draw_dim_v(c, sx, sy, ey, int(val), font_name, offset=10, font_size=5.5)
            py_d -= val

    # Total width dimension below
    total_w = sum(float(d) for i, d in enumerate(dims) if i % 2 == 0)
    sx, sy = to_page(0, min(ys))
    ex, ey = to_page(max(xs), min(ys))
    _draw_dim_h(c, sx, ex, sy - 8, int(total_w), font_name, offset=14, font_size=6.5)

    c.restoreState()


def _draw_bent_schematic(c, cx, cy, avail_w, avail_h, dims, font_name, bend_angle_deg: float = 93):
    """Draw bent-view schematic (installed/side look) centered in area."""
    if not dims or len(dims) < 3:
        return

    total = sum(float(d) for d in dims) or 1
    scale = min(avail_w, avail_h) * 0.7 / total

    vert_dims = [float(dims[i]) for i in range(1, len(dims), 2)]
    horiz_dims = [float(dims[i]) for i in range(0, len(dims), 2)]

    total_height = sum(vert_dims)
    top_flange = float(dims[0]) if len(dims) > 0 else 0
    bot_flange = float(dims[-1]) if len(dims) % 2 == 1 and len(dims) > 2 else 0

    h_scaled = total_height * scale
    top_scaled = top_flange * scale
    bot_scaled = bot_flange * scale

    x0 = cx - max(top_scaled, bot_scaled) / 2
    y0 = cy - h_scaled / 2

    c.saveState()
    c.setLineWidth(1.5)
    c.setStrokeColorRGB(0, 0, 0)

    c.line(x0, y0 + h_scaled, x0 + top_scaled, y0 + h_scaled)
    c.line(x0, y0 + h_scaled, x0, y0)
    c.line(x0, y0, x0 + bot_scaled, y0)

    _draw_dim_v(c, x0 + max(top_scaled, bot_scaled) + 3, y0, y0 + h_scaled,
                int(total_height), font_name, offset=10, font_size=5.5)
    if top_flange > 0:
        _draw_dim_h(c, x0, x0 + top_scaled, y0 + h_scaled + 3, int(top_flange),
                    font_name, offset=8, font_size=5.5)

    ang = int(bend_angle_deg) if bend_angle_deg else 93
    c.setFont(font_name, 6)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(x0 + top_scaled / 2, y0 + h_scaled - 4, f"{ang}°")

    c.restoreState()


def _draw_fallback_bent_schematic(
    c, cx, cy, avail_w, avail_h, bend_angle_deg: float, font_name: str,
) -> None:
    """L-shaped bend hint when profile_dimensions are missing (matches shop 'bend after flat' wording)."""
    c.saveState()
    ang = int(bend_angle_deg) if bend_angle_deg else 93
    leg = min(float(avail_w), float(avail_h)) * 0.42
    if leg < 18:
        leg = 18.0
    x0 = cx - leg * 0.15
    y0 = cy - leg * 0.38
    c.setLineWidth(2.2)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x0, y0 + leg, x0, y0)
    c.line(x0, y0, x0 + leg, y0)
    c.setFont(font_name, 7)
    c.setFillColorRGB(0.15, 0.15, 0.15)
    c.drawCentredString(x0 + leg * 0.38, y0 + leg * 0.48, f"{ang}°")
    c.restoreState()


def _draw_flat_layout(c, cx, cy, avail_w, avail_h, length, width, font_name):
    """Draw flat layout rectangle with red dashed border and dimensions."""
    if length <= 0 or width <= 0:
        return
    scale = min((avail_w - 40) / length, (avail_h - 40) / width) * 0.8
    rw = length * scale
    rh = width * scale
    rx = cx - rw / 2
    ry = cy - rh / 2

    c.saveState()
    c.setStrokeColorRGB(0.8, 0, 0)
    c.setLineWidth(1.0)
    c.setDash(6, 3)
    c.rect(rx, ry, rw, rh)
    c.setDash()
    c.setFillColorRGB(0.97, 0.93, 0.93)
    c.rect(rx, ry, rw, rh, fill=1, stroke=0)
    c.setStrokeColorRGB(0.8, 0, 0)
    c.setDash(6, 3)
    c.setLineWidth(1.0)
    c.rect(rx, ry, rw, rh, fill=0, stroke=1)
    c.setDash()

    # Length dimension (horizontal, below)
    _draw_dim_h(c, rx, rx + rw, ry, int(length), font_name, offset=14, font_size=6.5)
    # Width dimension (vertical, right)
    _draw_dim_v(c, rx + rw, ry, ry + rh, int(width), font_name, offset=14, font_size=6.5)

    c.setFont(font_name, 7)
    c.setFillColorRGB(0.5, 0, 0)
    c.drawCentredString(cx, ry + rh + 5, _visual("פריסה שטוחה"))
    c.restoreState()


def _draw_info_table(c, x0, y0, w, h, panel, index, header, length, width, area, font_name):
    """Draw professional data table at bottom of page."""
    thick = header.get("thickness_mm") or 2
    ral = header.get("color_ral") or "9011"
    name = panel_name(panel, index)
    qty = int(panel.get("quantity") or 1)
    proj_id = header.get("project_id") or ""
    proj_name = header.get("project_name") or ""
    client = header.get("client_name") or ""
    date = header.get("date") or ""
    mat = header.get("material") or "אלומיניום"
    notes = panel.get("notes") or ""

    c.saveState()

    num_cols = 8
    col_w = w / num_cols
    row_h = h / 3

    headers_heb = ["הערות", 'שטח מ"ר', "כמות", "צבע", "עובי", 'רוחב מ"מ', 'אורך מ"מ', "שם המוצר"]
    values = [
        notes, f"{area:.4f}", str(qty), f"RAL {ral}",
        f'{thick} מ"מ', str(int(width)) if width else "-",
        str(int(length)), f"{name} x{qty}",
    ]
    layout = (header.get("layout_sheet_id") or "").strip()
    loc = (header.get("location") or "").strip()
    proj_line = f"{proj_id} {proj_name}".strip() or (client or "")
    info_labels = [
        _visual(mat),
        _visual(layout) if layout else "",
        _visual(loc) if loc else "",
        "",
        _visual("תאריך:"),
        _visual(date),
        _visual("פרויקט:"),
        _visual(proj_line),
    ]

    dark_blue = rl_colors.HexColor("#1F4E79")
    light_blue = rl_colors.HexColor("#D9E1F2")

    # Header row background
    c.setFillColor(dark_blue)
    c.rect(x0, y0 + 2 * row_h, w, row_h, fill=1, stroke=0)

    # Data row background
    c.setFillColor(rl_colors.white)
    c.rect(x0, y0 + row_h, w, row_h, fill=1, stroke=0)

    # Info row background
    c.setFillColor(light_blue)
    c.rect(x0, y0, w, row_h, fill=1, stroke=0)

    # Grid
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.5)
    for r in range(4):
        c.line(x0, y0 + r * row_h, x0 + w, y0 + r * row_h)
    for col in range(num_cols + 1):
        c.line(x0 + col * col_w, y0, x0 + col * col_w, y0 + 3 * row_h)

    # Outer border
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(1.0)
    c.rect(x0, y0, w, 3 * row_h)

    # Header text (white on dark blue)
    c.setFillColor(rl_colors.white)
    c.setFont(font_name, 7)
    for i, label in enumerate(headers_heb):
        cx = x0 + (num_cols - 1 - i) * col_w + col_w / 2
        cy = y0 + 2.5 * row_h - 3
        c.drawCentredString(cx, cy, _visual(label))

    # Data text
    c.setFillColorRGB(0, 0, 0)
    c.setFont(font_name, 8)
    for i, val in enumerate(values):
        cx = x0 + (num_cols - 1 - i) * col_w + col_w / 2
        cy = y0 + 1.5 * row_h - 3
        c.drawCentredString(cx, cy, _visual(val))

    # Info row text
    c.setFont(font_name, 7)
    for i, val in enumerate(info_labels):
        cx = x0 + (num_cols - 1 - i) * col_w + col_w / 2
        cy = y0 + 0.5 * row_h - 3
        c.drawCentredString(cx, cy, val)

    c.restoreState()


def create_panel_pdf(panel: dict, index: int, header: dict, output_path: Path) -> None:
    """Create professional PDF drawing sheet for a panel."""
    length = float(panel.get("length_mm") or 0)
    width = get_width(panel)
    dims = panel.get("profile_dimensions")
    name = panel_name(panel, index)
    qty = int(panel.get("quantity") or 1)
    thick = header.get("thickness_mm") or 2
    ral = header.get("color_ral") or "9011"
    font_name = _register_hebrew_font()
    area = (length * width * qty) / 1_000_000 if width else 0

    c = canvas.Canvas(str(output_path), pagesize=A4)
    page_w, page_h = A4
    margin = 12 * mm

    # ── Page border ──
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.5)
    c.rect(margin, margin, page_w - 2 * margin, page_h - 2 * margin)

    inner_l = margin + 4 * mm
    inner_r = page_w - margin - 4 * mm
    inner_w = inner_r - inner_l

    # ── Title block (top right) ──
    title_y = page_h - margin - 8 * mm
    bend_deg = int(panel.get("bend_angle_deg") or 93)

    c.setFont(font_name, 13)
    c.drawRightString(inner_r, title_y, _visual(f"פרופיל {name}  x{qty}"))
    c.setFont(font_name, 8)
    c.drawRightString(
        inner_r,
        title_y - 14,
        _visual(f"פריסה שטוחה לפני כיפוף – חותכים ומכופפים {bend_deg}°"),
    )
    c.setFont(font_name, 7)
    c.drawRightString(
        inner_r,
        title_y - 26,
        _visual(f'Al {thick} mm   |   RAL {ral}   |   {header.get("project_id") or ""}'),
    )
    extra_y = title_y - 38
    loc_txt = (header.get("location") or "").strip()
    lay_txt = (header.get("layout_sheet_id") or "").strip()
    if loc_txt:
        c.drawRightString(inner_r, extra_y, _visual(f"מיקום: {loc_txt}"))
        extra_y -= 11
    if lay_txt:
        c.drawRightString(inner_r, extra_y, _visual(f"פריסה חומר: {lay_txt}"))
        extra_y -= 11

    # ── Separator ──
    sep_y = extra_y - 8
    c.setLineWidth(0.6)
    c.line(margin, sep_y, page_w - margin, sep_y)

    # ── Layout zones ──
    table_h = 38 * mm
    table_y = margin + 6 * mm
    table_top = table_y + table_h

    # Separator above table
    c.setLineWidth(0.6)
    c.line(margin, table_top + 4 * mm, page_w - margin, table_top + 4 * mm)

    draw_top = sep_y - 5 * mm
    draw_bot = table_top + 8 * mm
    draw_h = draw_top - draw_bot
    mid_x = page_w / 2

    # ── Left zone: Cross-section view ──
    section_cx = margin + (mid_x - margin) / 2
    section_cy = draw_bot + draw_h * 0.55
    section_w = mid_x - margin - 10 * mm
    section_h = draw_h * 0.75

    if dims and len(dims) >= 2:
        _draw_profile_view(c, section_cx, section_cy, section_w, section_h, dims, font_name)
        # Label
        c.setFont(font_name, 7)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(section_cx, draw_bot + 5, _visual("חתך פרופיל"))

    # ── Right zone: Flat layout rectangle ──
    flat_cx = mid_x + (page_w - margin - mid_x) / 2
    flat_cy = draw_bot + draw_h * 0.55
    flat_w = page_w - margin - mid_x - 10 * mm
    flat_h = draw_h * 0.70

    _draw_flat_layout(c, flat_cx, flat_cy, flat_w, flat_h, length, width, font_name)

    # ── Bent schematic (small, below cross-section) — always show bent intent
    bent_cx = inner_l + 35 * mm
    bent_cy = draw_bot + draw_h * 0.12
    bent_w, bent_h = 50 * mm, draw_h * 0.22
    if dims and len(dims) >= 3:
        _draw_bent_schematic(
            c, bent_cx, bent_cy, bent_w, bent_h, dims, font_name,
            bend_angle_deg=float(panel.get("bend_angle_deg") or 93),
        )
    else:
        _draw_fallback_bent_schematic(
            c, bent_cx, bent_cy, bent_w, bent_h, float(panel.get("bend_angle_deg") or 93), font_name,
        )
    c.setFont(font_name, 6)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(bent_cx, bent_cy - draw_h * 0.13, _visual("מבט צד (כפוף)"))

    # ── Data table (bottom) ──
    _draw_info_table(c, margin + 2 * mm, table_y, page_w - 2 * margin - 4 * mm,
                     table_h, panel, index, header, length, width, area, font_name)

    c.showPage()
    c.save()


# ── Orchestrator ──────────────────────────────────────────────────────────────

def create_dxf_files(data: dict, project_id: str, output_dir: Path) -> dict[str, list[Path]]:
    """Create DXF + PDF for each panel. Returns dxf and pdf path lists (panel order)."""
    output_dir = Path(output_dir)
    dwg_dir = output_dir / "dwg"
    pdf_dir = output_dir / "pdf_panels"
    dwg_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    header = data.get("header", {})
    panels = data.get("panels", [])
    dxf_paths = []
    pdf_paths = []

    for i, panel in enumerate(panels):
        safe_name = panel_name(panel, i).replace("/", "-").replace("\\", "-")
        dxf_path = dwg_dir / f"{project_id}-{safe_name}.dxf"
        pdf_path = pdf_dir / f"{project_id}-{safe_name}.pdf"

        create_panel_dxf(panel, i, header, dxf_path)
        create_panel_pdf(panel, i, header, pdf_path)

        dxf_paths.append(dxf_path)
        pdf_paths.append(pdf_path)

    # ZIP DXF
    zip_path = output_dir / f"DWG-{project_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in dxf_paths:
            zf.write(p, p.name)

    # ZIP PDF panels
    pdf_zip_path = output_dir / f"PDF-{project_id}.zip"
    with zipfile.ZipFile(pdf_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pdf_paths:
            zf.write(p, p.name)

    return {"dxf": dxf_paths, "pdf": pdf_paths}
