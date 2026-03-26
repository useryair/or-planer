import json
from pathlib import Path

from src.planner_summary import build_planner_summary_rows, width_planning_status


def test_width_planning_status_locked():
    p = {"lock_flat_width_mm": True, "width_mm": 100}
    assert width_planning_status(p, {}, 999) == "נעול"


def test_notebook_example_planner_width_matches_input():
    """exemple/notebook_sketch_page.json: רוחב בקלט matches flat width (legacy horizontal + explicit width)."""
    path = Path(__file__).resolve().parent.parent / "exemple" / "notebook_sketch_page.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows, _, _ = build_planner_summary_rows(data["panels"], data["header"])
    assert len(rows) == 5
    for r in rows:
        assert r["מצב"] == "תואם", r


def test_build_planner_summary_automatic_width():
    panels = [
        {
            "length_mm": 2000,
            "quantity": 2,
            "panel_id": "P1",
            "profile_dimensions": [25, 20, 170, 20, 25],
        }
    ]
    header = {"thickness_mm": 2, "flat_pattern_mode": "developed"}
    rows, area, qty = build_planner_summary_rows(panels, header)
    assert len(rows) == 1
    assert rows[0]["מצב"] == "אוטומטי"
    assert rows[0]["רוחב בקלט"] == "—"
    assert qty == 2
    assert area > 0
