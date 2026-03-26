"""Soft validation hints for planner data quality."""
from src.validate import validate_order_data, validate_order_warnings


def test_validate_rejects_bad_profile_dimensions():
    data = {
        "header": {},
        "panels": [
            {"length_mm": 1000, "quantity": 1, "profile_dimensions": []},
        ],
    }
    ok, errs = validate_order_data(data)
    assert ok is False
    assert any("ריק" in e for e in errs)


def test_warnings_duplicate_panel_id():
    data = {
        "header": {"thickness_mm": 2},
        "panels": [
            {"length_mm": 1000, "quantity": 1, "panel_id": "A"},
            {"length_mm": 2000, "quantity": 2, "panel_id": "A"},
        ],
    }
    w = validate_order_warnings(data)
    assert any("חוזר" in x for x in w)


def test_validate_rejects_non_positive_length():
    data = {
        "header": {},
        "panels": [{"length_mm": 0, "quantity": 1, "width_mm": 100}],
    }
    ok, errs = validate_order_data(data)
    assert ok is False
    assert any("חיובי" in e for e in errs)


def test_validate_rejects_fractional_quantity():
    data = {
        "header": {},
        "panels": [{"length_mm": 1000, "quantity": 1.5, "width_mm": 100}],
    }
    ok, errs = validate_order_data(data)
    assert ok is False
    assert any("שלם" in e for e in errs)


def test_validate_rejects_zero_flat_width():
    data = {
        "header": {"flat_pattern_mode": "developed"},
        "panels": [
            {
                "length_mm": 1000,
                "quantity": 1,
                "panel_id": "Z",
            },
        ],
    }
    ok, errs = validate_order_data(data)
    assert ok is False
    assert any("רוחב פריסה" in e for e in errs)


def test_warnings_extreme_length():
    data = {
        "header": {},
        "panels": [{"length_mm": 30000, "quantity": 1, "width_mm": 100}],
    }
    w = validate_order_warnings(data)
    assert any("חריג" in x for x in w)


def test_warnings_width_mismatch_developed():
    data = {
        "header": {"thickness_mm": 2, "flat_pattern_mode": "developed"},
        "panels": [
            {
                "length_mm": 1000,
                "quantity": 1,
                "panel_id": "X",
                "profile_dimensions": [30, 1040, 270],
                "width_mm": 300,
            },
        ],
    }
    w = validate_order_warnings(data)
    assert any("רוחב מוזן" in x for x in w)
