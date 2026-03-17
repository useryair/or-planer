"""
OR Planer - אפליקציית ווב בעברית
העלאת תמונה/קובץ, חילוץ נתונים, עריכה, יצירת הזמנה.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OR Planer - תכנון הזמנות",
    page_icon="📐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* RTL for Hebrew */
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .stMarkdown, .stDataFrame,
    [data-testid="stExpander"] {
        direction: rtl;
    }
    /* Hide hamburger menu and footer on mobile for cleaner look */
    #MainMenu, footer { visibility: hidden; }
    /* Hide the Fork ribbon */
    [data-testid="stToolbar"] { display: none; }
    /* Mobile-friendly spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    /* Better button sizing for touch */
    .stButton > button {
        width: 100%;
        min-height: 3rem;
        font-size: 1.1rem;
    }
    .stDownloadButton > button {
        width: 100%;
        min-height: 2.8rem;
    }
    /* File uploader touch-friendly */
    [data-testid="stFileUploader"] {
        min-height: 4rem;
    }
    /* Input fields bigger on mobile */
    .stTextInput input {
        font-size: 1rem !important;
        min-height: 2.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.markdown("## 📐 OR Planer")
st.caption("תכנון הזמנות פרופילי אלומיניום – העלאת שרטוט, עריכה, יצירת קבצים")

# ── Project ID (inline, not in sidebar) ──
project_id = st.text_input("מזהה פרויקט", value="GPN-1")

# ── File upload ──
st.markdown("---")
uploaded_files = st.file_uploader(
    "העלאת תמונות שרטוט או JSON",
    type=["jpg", "jpeg", "png", "json"],
    accept_multiple_files=True,
)

data = None

if uploaded_files:
    files = list(uploaded_files)
    images = [f for f in files if f.name.lower().endswith((".jpg", ".jpeg", ".png"))]
    jsons = [f for f in files if f.name.lower().endswith(".json")]

    if jsons and not images:
        try:
            data = json.load(jsons[0])
            st.success(f"JSON נטען ({jsons[0].name})")
        except json.JSONDecodeError as e:
            st.error(f"שגיאה: {e}")
    elif images:
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
                    for img in images:
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
                    st.success(f"חולצו {len(all_panels)} פנלים")
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                        st.error("מכסת API נגמרה. העלה JSON במקום תמונה.")
                    elif "503" in err_msg or "UNAVAILABLE" in err_msg:
                        st.error("השרת עמוס. נסה שוב בעוד דקה.")
                    else:
                        st.error(f"שגיאה: {e}")
    else:
        st.warning("העלה תמונות (JPG/PNG) או קובץ JSON")

if data:
    upload_key = "_".join(f"{f.name}_{f.size}" for f in uploaded_files) if uploaded_files else ""
    if "edit_data" not in st.session_state or st.session_state.get("upload_key") != upload_key:
        st.session_state["edit_data"] = json.loads(json.dumps(data, ensure_ascii=False))
        st.session_state["upload_key"] = upload_key

    edit_data = st.session_state["edit_data"]

    from src.validate import validate_order_data
    valid, errors = validate_order_data(edit_data)
    if not valid:
        st.warning("מלא את השדות החסרים:")
        for e in errors:
            st.write(f"• {e}")

    # ── Header editing ──
    st.markdown("---")
    with st.expander("✏️ פרטי הזמנה", expanded=not valid):
        header = edit_data.get("header", {})
        header["project_id"] = st.text_input("מזהה פרויקט ", value=str(header.get("project_id") or project_id))
        header["client_name"] = st.text_input("שם לקוח", value=str(header.get("client_name") or ""))
        header["project_name"] = st.text_input("שם פרויקט", value=str(header.get("project_name") or ""))
        header["date"] = st.text_input("תאריך", value=str(header.get("date") or ""))

        c1, c2 = st.columns(2)
        with c1:
            header["color_ral"] = st.text_input("צבע RAL", value=str(header.get("color_ral") or "9011"))
            header["material"] = st.text_input("חומר", value=str(header.get("material") or "אלומיניום"))
        with c2:
            header["order_number"] = st.text_input("מספר הזמנה", value=str(header.get("order_number") or ""))
            thick_val = header.get("thickness_mm") or 2
            thick_in = st.text_input('עובי מ"מ', value=str(int(thick_val)))
            try:
                header["thickness_mm"] = int(thick_in) if thick_in else int(thick_val)
            except ValueError:
                header["thickness_mm"] = int(thick_val)

    # ── Panel editing ──
    with st.expander("✏️ פנלים", expanded=True):
        panels = edit_data.get("panels", [])
        if panels:
            def _dims_str(p):
                d = p.get("profile_dimensions")
                return ",".join(str(x) for x in d) if d else ""

            rows = []
            for i, p in enumerate(panels):
                length_val = p.get("length_mm")
                width_val = p.get("width_mm")
                qty_val = p.get("quantity")
                rows.append({
                    "#": str(i + 1),
                    "מק\"ט": str(p.get("panel_id") or ""),
                    "אורך": str(int(length_val)) if length_val is not None else "",
                    "רוחב": str(int(width_val)) if width_val is not None else "",
                    "כמות": str(int(qty_val)) if qty_val is not None else "1",
                    "סובב": str(p.get("turn") or "N"),
                    "פרופיל": _dims_str(p),
                    "הערות": str(p.get("notes") or ""),
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                use_container_width=True,
                column_config={
                    "#": st.column_config.TextColumn(disabled=True, width="small"),
                    "אורך": st.column_config.TextColumn(width="small"),
                    "רוחב": st.column_config.TextColumn(width="small"),
                    "כמות": st.column_config.TextColumn(width="small"),
                    "סובב": st.column_config.TextColumn(width="small"),
                    "פרופיל": st.column_config.TextColumn(help="25,20,170,20,25"),
                },
                num_rows="dynamic",
            )

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
                dims_str = str(row.get("פרופיל", "") or "").strip()
                profile_dimensions = None
                if dims_str:
                    try:
                        profile_dimensions = [float(x.strip()) for x in dims_str.split(",") if x.strip()]
                    except ValueError:
                        pass
                pid = str(row["מק\"ט"]).strip() if pd.notna(row["מק\"ט"]) else ""
                new_panels.append({
                    "panel_id": pid if pid else None,
                    "length_mm": _parse_num(row["אורך"]),
                    "width_mm": _parse_num(row["רוחב"]),
                    "quantity": _parse_int(row["כמות"], 1),
                    "turn": str(row["סובב"]).strip() if pd.notna(row["סובב"]) else "N",
                    "notes": str(row["הערות"]).strip() if pd.notna(row["הערות"]) else "",
                    "profile_dimensions": profile_dimensions,
                    "profile_type": None,
                    "bend_angle_deg": 93,
                    "bend_offset_mm": 30,
                })
            edit_data["panels"] = new_panels
            edit_data["header"] = header
            st.session_state["edit_data"] = edit_data

    # ── Summary ──
    st.markdown("---")
    st.markdown("### סיכום")
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
                "אורך": int(length),
                "רוחב": int(width),
                "כמות": qty,
                'שטח מ"ר': round(area, 2),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # ── Generate ──
    st.markdown("---")
    if st.button("צור הזמנה", type="primary"):
        with st.spinner("יוצר קבצים..."):
            try:
                from src.output import generate_output
                output_dir = Path("output") / project_id
                output_dir.mkdir(parents=True, exist_ok=True)
                gen_data = st.session_state["edit_data"]
                if "header" not in gen_data:
                    gen_data["header"] = {}
                gen_data["header"]["project_id"] = gen_data["header"].get("project_id") or project_id
                result = generate_output(gen_data, project_id, output_dir)
                st.success("הקבצים נוצרו!")

                excel_path = Path(result["excel"])
                pdf_path = Path(result["pdf"])

                c1, c2 = st.columns(2)
                with c1:
                    if excel_path.exists():
                        with open(excel_path, "rb") as f:
                            st.download_button("Excel", f, file_name=excel_path.name,
                                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                with c2:
                    if pdf_path.exists():
                        with open(pdf_path, "rb") as f:
                            st.download_button("PDF", f, file_name=pdf_path.name, mime="application/pdf")

                c3, c4 = st.columns(2)
                with c3:
                    if "dxf_zip" in result:
                        zip_path = Path(result["dxf_zip"])
                        if zip_path.exists():
                            with open(zip_path, "rb") as f:
                                st.download_button("DXF (ZIP)", f, file_name=zip_path.name, mime="application/zip")
                with c4:
                    if "pdf_zip" in result:
                        pdf_zip_path = Path(result["pdf_zip"])
                        if pdf_zip_path.exists():
                            with open(pdf_zip_path, "rb") as f:
                                st.download_button("PDF panels (ZIP)", f, file_name=pdf_zip_path.name, mime="application/zip")
            except Exception as e:
                st.error(f"שגיאה: {e}")
                st.exception(e)

else:
    st.info("העלה תמונות שרטוט או קובץ JSON כדי להתחיל")

# ── Footer ──
st.markdown("---")
st.caption("OR Planer v1.0 | Salvado Yafo")
