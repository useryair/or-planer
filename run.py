"""
Full pipeline: extract from image -> generate Excel + PDF.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.extract import extract_from_image
from src.output import generate_output
from src.validate import validate_and_raise, validate_order_warnings


def run(image_path: str, project_id: str = "MR277-3", output_dir: str = "output"):
    """Extract from image and generate output files."""
    output_path = Path(output_dir) / project_id
    output_path.mkdir(parents=True, exist_ok=True)

    print("1. Extracting from image...")
    data = extract_from_image(image_path)
    print("   Done. Panels:", len(data.get("panels", [])))

    # Save JSON for review
    json_path = output_path / "extracted.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("   Saved:", json_path)

    validate_and_raise(data)
    warns = validate_order_warnings(data)
    if warns:
        print("   אזהרות עקביות (לא חוסמות):")
        for w in warns:
            print("    •", w)
    print("2. Generating Excel + PDF...")
    result = generate_output(data, project_id, output_path)
    print("   Done.")
    return result


def run_from_json(json_path: str, project_id: str = "MR277-3", output_dir: str = "output"):
    """Generate output from existing JSON (skip extraction)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    validate_and_raise(data)
    warns = validate_order_warnings(data)
    if warns:
        print("אזהרות עקביות (לא חוסמות):")
        for w in warns:
            print("  •", w)
    output_path = Path(output_dir) / project_id
    output_path.mkdir(parents=True, exist_ok=True)
    print("Generating Excel + PDF from JSON...")
    result = generate_output(data, project_id, output_path)
    print("   Excel: Created")
    print("   PDF: Created")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run.py <image_path|json_path> [project_id]")
        print("  image: python run.py \"or planer/1000047706.jpg\" GPN-1")
        print("  json:  python run.py output/extracted.json GPN-1")
        sys.exit(1)

    input_path = sys.argv[1]
    project_id = sys.argv[2] if len(sys.argv) > 2 else "MR277-3"

    if input_path.lower().endswith(".json"):
        run_from_json(input_path, project_id)
    else:
        run(input_path, project_id)
