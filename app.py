"""
OR Planer - אפליקציית ווב בעברית
העלאת תמונה/קובץ, חילוץ נתונים, עריכה, יצירת הזמנה.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

# RTL + Hebrew
st.set_page_config(
    page_title="OR Planer - תכנון הזמנות",
    page_icon="📐",
    layout="wide",
)

# Custom CSS for RTL
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { direction: rtl; }
    [data-testid="stHeader"] { direction: rtl; }
    .stMarkdown, .stDataFrame { direction: rtl; }
</style>
""", unsafe_allow_html=True)

st.title("📐 OR Planer")
st.markdown("**תכנון הזמנות פרופילי אלומיניום** – העלאת שרטוט, חילוץ נתונים, **עריכה והוספת נתונים חסרים**, יצירת קבצים לספק")

# Sidebar
with st.sidebar:
    st.header("הגדרות")
    project_id = st.text_input("מזהה פרויקט", value="GPN-1", help="למשל GPN-1, MR277-3")
    st.divider()
    st.caption("העלה תמונות שרטוט (JPG/PNG) או קובץ JSON – ניתן לבחור מספר קבצים")
    with st.expander("אין מכסת API? השתמש ב-JSON"):
        st.caption("אם נגמרה המכסה היומית (20 תמונות), העלה קובץ JSON במקום. אין צורך ב-API.")
        st.caption("דוגמה: output/GPN-1/extracted.json")

# File upload - multiple files allowed
uploaded_files = st.file_uploader(
    "העלאת קבצים",
    type=["jpg", "jpeg", "png", "json"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

data = None

if uploaded_files:
    files = list(uploaded_files)
    images = [f for f in files if f.name.lower().endswith((".jpg", ".jpeg", ".png"))]
    jsons = [f for f in files if f.name.lower().endswith(".json")]

    if jsons and not images:
        try:
            data = json.load(jsons[0])
            st.success(f"קובץ JSON נטען בהצלחה ({jsons[0].name})")
        except json.JSONDecodeError as e:
            st.error(f"שגיאה בקובץ JSON: {e}")
    elif images:
        # Cache extraction - do NOT re-extract on every edit (causes 503 when typing)
        upload_key = "_".join(f"{f.name}_{f.size}" for f in images)
        if "extracted_cache" not in st.session_state:
            st.session_state["extracted_cache"] = {}
        if upload_key in st.session_state["extracted_cache"]:
            data = st.session_state["extracted_cache"][upload_key]
        else:
            with st.spinner(f"מחלץ נתונים מ-{len(images)} תמונות..."):
                try:
                    from src.extract import extract_from_image
                    import tempfile
                    all_panels = []
                    header = None
                    for i, img in enumerate(images):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(img.read())
                            tmp_path = tmp.name
                        extracted = extract_from_image(tmp_path)
                        Path(tmp_path).unlink(missing_ok=True)
                        if header is None:
                            header = extracted.get("header", {})
                        all_panels.extend(extracted.get("panels", []))
                    data = {"header": header or {}, "panels": all_panels}
                    st.session_state["extracted_cache"][upload_key] = data
                    st.success(f"חולצו {len(all_panels)} פנלים מ-{len(images)} תמונות – ניתן לערוך נתונים חסרים למטה")
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                        st.error(
                            "מכסת ה-API היומית (20 בקשות) נגמרה. "
                            "**פתרון:** העלה קובץ JSON במקום תמונה – אין צורך ב-API. "
                            "אפשר להעתיק את המבנה מ-output/GPN-1/extracted.json"
                        )
                    elif "503" in err_msg or "UNAVAILABLE" in err_msg or "high demand" in err_msg.lower():
                        st.error("המודל של Google עמוס כרגע. נסה שוב בעוד דקה־שתיים.")
                    else:
                        st.error(f"שגיאה בחילוץ: {e}")
                    st.exception(e)
    else:
        st.warning("העלה תמונות (JPG/PNG) או קובץ JSON")

if data:
    # Initialize session state for editable data (reset when new files uploaded)
    upload_key = "_".join(f"{f.name}_{f.size}" for f in uploaded_files) if uploaded_files else ""
    if "edit_data" not in st.session_state or st.session_state.get("upload_key") != upload_key:
        st.session_state["edit_data"] = json.loads(json.dumps(data, ensure_ascii=False))
        st.session_state["upload_key"] = upload_key

    edit_data = st.session_state["edit_data"]

    # Validate
    from src.validate import validate_order_data
    valid, errors = validate_order_data(edit_data)
    if not valid:
        st.warning("שגיאות באימות – מלא את השדות החסרים בסעיף העריכה:")
        for e in errors:
            st.write(f"• {e}")

    # --- עריכה והוספת נתונים חסרים ---
    with st.expander("✏️ עריכה והוספת נתונים חסרים", expanded=not valid):
        st.caption("💡 במובייל: גע בשדה הרצוי ואז הקלד. כל השדות מקבלים הקלדה ממקלדת.")
        header = edit_data.get("header", {})
        h1, h2 = st.columns(2)
        with h1:
            header["project_id"] = st.text_input("מזהה פרויקט", value=str(header.get("project_id") or project_id))
            header["client_name"] = st.text_input("שם לקוח", value=str(header.get("client_name") or ""))
            header["project_name"] = st.text_input("שם פרויקט", value=str(header.get("project_name") or ""))
            header["date"] = st.text_input("תאריך", value=str(header.get("date") or ""))
        with h2:
            header["color_ral"] = st.text_input("צבע RAL", value=str(header.get("color_ral") or "9011"))
            header["order_number"] = st.text_input("מספר הזמנה", value=str(header.get("order_number") or ""))
            header["material"] = st.text_input("חומר", value=str(header.get("material") or "אלומיניום"))
            thick_val = header.get("thickness_mm") or 2
            thick_in = st.text_input("עובי מ\"מ", value=str(int(thick_val)), help="הקלד 1-5")
            try:
                header["thickness_mm"] = int(thick_in) if thick_in else int(thick_val)
            except ValueError:
                header["thickness_mm"] = int(thick_val)

        st.subheader("פנלים – עריכה")
        panels = edit_data.get("panels", [])
        if panels:
            # Build editable table
            def _dims_str(p):
                d = p.get("profile_dimensions")
                if d is None:
                    return ""
                return ",".join(str(x) for x in d)

            # Use TEXT for numeric columns - better keyboard input on mobile
            rows = []
            for i, p in enumerate(panels):
                length_val = p.get("length_mm")
                width_val = p.get("width_mm")
                qty_val = p.get("quantity")
                rows.append({
                    "#": str(i + 1),
                    "מק\"ט": str(p.get("panel_id") or ""),
                    "אורך מ\"מ": str(int(length_val)) if length_val is not None else "",
                    "רוחב מ\"מ": str(int(width_val)) if width_val is not None else "",
                    "כמות": str(int(qty_val)) if qty_val is not None else "1",
                    "לסובב": str(p.get("turn") or "N"),
                    "מידות פרופיל (מופרדות בפסיק)": _dims_str(p),
                    "הערות": str(p.get("notes") or ""),
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                use_container_width=True,
                column_config={
                    "#": st.column_config.TextColumn(disabled=True),
                    "אורך מ\"מ": st.column_config.TextColumn(label="אורך מ\"מ", help="הקלד מספר"),
                    "רוחב מ\"מ": st.column_config.TextColumn(label="רוחב מ\"מ", help="הקלד מספר או השאר ריק"),
                    "כמות": st.column_config.TextColumn(label="כמות", help="הקלד מספר"),
                    "מידות פרופיל (מופרדות בפסיק)": st.column_config.TextColumn(help="למשל: 25,20,170,20,25"),
                },
                num_rows="dynamic",
            )

            # Convert back to panels (parse text to numbers)
            def _parse_num(val, default=None):
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return default
                s = str(val).strip()
                if not s:
                    return default
                try:
                    return float(s)
                except ValueError:
                    return default

            def _parse_int(val, default=1):
                n = _parse_num(val, default)
                return int(n) if n is not None else default

            new_panels = []
            for _, row in edited.iterrows():
                dims_str = str(row.get("מידות פרופיל (מופרדות בפסיק)", "") or "").strip()
                profile_dimensions = None
                if dims_str:
                    try:
                        profile_dimensions = [float(x.strip()) for x in dims_str.split(",") if x.strip()]
                    except ValueError:
                        pass
                pid = str(row["מק\"ט"]).strip() if pd.notna(row["מק\"ט"]) else ""
                new_panels.append({
                    "panel_id": pid if pid else None,
                    "length_mm": _parse_num(row["אורך מ\"מ"]),
                    "width_mm": _parse_num(row["רוחב מ\"מ"]),
                    "quantity": _parse_int(row["כמות"], 1),
                    "turn": str(row["לסובב"]).strip() if pd.notna(row["לסובב"]) else "N",
                    "notes": str(row["הערות"]).strip() if pd.notna(row["הערות"]) else "",
                    "profile_dimensions": profile_dimensions,
                    "profile_type": None,
                    "bend_angle_deg": 93,
                    "bend_offset_mm": 30,
                })
            edit_data["panels"] = new_panels
            edit_data["header"] = header
            st.session_state["edit_data"] = edit_data

    # Show summary (read-only)
    st.subheader("סיכום")
    panels = edit_data.get("panels", [])
    if panels:
        from src.output import get_width, panel_name
        rows = []
        for i, p in enumerate(panels):
            length = float(p.get("length_mm") or 0)
            width = get_width(p)
            qty = int(p.get("quantity") or 1)
            area = (length * width * qty) / 1_000_000 if width else 0
            rows.append({
                "#": i + 1,
                "שם": panel_name(p, i),
                "אורך מ\"מ": length,
                "רוחב מ\"מ": width,
                "כמות": qty,
                "שטח מ\"ר": round(area, 2),
                "הערות": p.get("notes") or "",
            })
        st.dataframe(rows, use_container_width=True)

    # Generate
    st.divider()
    if st.button("צור הזמנה", type="primary"):
        with st.spinner("יוצר קבצים..."):
            try:
                from src.output import generate_output
                output_dir = Path("output") / project_id
                output_dir.mkdir(parents=True, exist_ok=True)
                # Use edited data
                gen_data = st.session_state["edit_data"]
                if "header" not in gen_data:
                    gen_data["header"] = {}
                gen_data["header"]["project_id"] = gen_data["header"].get("project_id") or project_id
                result = generate_output(gen_data, project_id, output_dir)
                st.success("הקבצים נוצרו בהצלחה!")

                # Download buttons
                excel_path = Path(result["excel"])
                pdf_path = Path(result["pdf"])
                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    if excel_path.exists():
                        with open(excel_path, "rb") as f:
                            st.download_button("הורד Excel", f, file_name=excel_path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                with d2:
                    if pdf_path.exists():
                        with open(pdf_path, "rb") as f:
                            st.download_button("הורד PDF", f, file_name=pdf_path.name, mime="application/pdf")
                with d3:
                    if "dxf_zip" in result:
                        zip_path = Path(result["dxf_zip"])
                        if zip_path.exists():
                            with open(zip_path, "rb") as f:
                                st.download_button("הורד ZIP (DXF)", f, file_name=zip_path.name, mime="application/zip")
                with d4:
                    if "pdf_zip" in result:
                        pdf_zip_path = Path(result["pdf_zip"])
                        if pdf_zip_path.exists():
                            with open(pdf_zip_path, "rb") as f:
                                st.download_button("הורד ZIP (PDF)", f, file_name=pdf_zip_path.name, mime="application/zip")
            except Exception as e:
                st.error(f"שגיאה: {e}")
                st.exception(e)

else:
    st.info("העלה תמונות שרטוט (ניתן לבחור כמה) או קובץ JSON כדי להתחיל")
