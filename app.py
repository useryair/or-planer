"""
OR Planer - Professional aluminum cladding order planner
"""
import json
import base64
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="OR Planer - תכנון הזמנות",
    page_icon="📐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Theme CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    :root {
        --primary: #1F4E79;
        --accent: #4A90D9;
        --success: #27AE60;
        --surface: #F8F9FA;
        --border: #E2E8F0;
        --text: #1A202C;
        --text-muted: #718096;
    }

    /* RTL */
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .stMarkdown, .stDataFrame,
    [data-testid="stExpander"] {
        direction: rtl;
    }

    /* Hide chrome */
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stToolbar"] { display: none; }

    /* Layout */
    .block-container {
        padding-top: 0 !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }

    /* Card containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
        border-color: var(--border) !important;
        background: white !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600 !important;
    }

    /* Buttons */
    .stButton > button {
        width: 100%;
        min-height: 2.8rem;
        font-size: 1rem;
        border-radius: 8px !important;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .stDownloadButton > button {
        width: 100%;
        min-height: 2.6rem;
        border-radius: 8px !important;
        font-weight: 500;
    }

    /* Generate button emphasis */
    .generate-btn .stButton > button {
        min-height: 3.2rem !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        min-height: 4rem;
    }
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 10px !important;
        border: 2px dashed var(--border) !important;
        background: var(--surface) !important;
    }

    /* Inputs */
    .stTextInput input {
        font-size: 1rem !important;
        min-height: 2.4rem !important;
        border-radius: 8px !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: var(--surface);
        padding: 0.7rem 0.9rem;
        border-radius: 10px;
        border: 1px solid var(--border);
        text-align: center;
    }
    [data-testid="stMetricLabel"] {
        justify-content: center;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }

    /* Data editor */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        overflow: hidden;
    }

    /* Section heading helper */
    .section-head {
        font-size: 0.85rem;
        font-weight: 700;
        color: #4A5568;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.3rem;
        padding-right: 0.2rem;
    }

    /* Banner */
    .app-banner {
        background: linear-gradient(135deg, #1F4E79 0%, #2D6DA3 100%);
        color: white;
        padding: 1.4rem 1.2rem 1rem;
        border-radius: 0 0 16px 16px;
        margin: -1rem -1rem 1rem -1rem;
        text-align: center;
        box-shadow: 0 2px 12px rgba(31,78,121,0.25);
    }
    .app-banner h1 {
        margin: 0;
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: 0.02em;
    }
    .app-banner p {
        margin: 0.3rem 0 0;
        font-size: 0.85rem;
        opacity: 0.85;
    }

    /* Step indicator */
    .steps-bar {
        display: flex;
        justify-content: center;
        gap: 0;
        margin: 0.8rem 0 0.4rem;
        direction: ltr;
    }
    .step-item {
        display: flex;
        align-items: center;
        font-size: 0.72rem;
        font-weight: 600;
        color: rgba(255,255,255,0.45);
        transition: color 0.2s;
    }
    .step-item.active {
        color: #FFFFFF;
    }
    .step-item.done {
        color: #90EE90;
    }
    .step-arrow {
        margin: 0 0.4rem;
        font-size: 0.6rem;
        color: rgba(255,255,255,0.3);
    }

    /* Preview file cards */
    .file-card {
        display: flex;
        align-items: center;
        padding: 0.65rem 0.8rem;
        border-radius: 8px;
        border: 1px solid var(--border);
        margin-bottom: 0.4rem;
        background: white;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .file-card:hover { background: var(--surface); }
    .file-card .file-icon {
        font-size: 1.3rem;
        margin-left: 0.7rem;
        width: 2rem;
        text-align: center;
    }
    .file-card .file-info { flex: 1; }
    .file-card .file-name {
        font-weight: 600;
        font-size: 0.88rem;
        color: var(--text);
    }
    .file-card .file-meta {
        font-size: 0.72rem;
        color: var(--text-muted);
    }
    .fc-pdf { border-right: 3px solid #E53E3E; }
    .fc-excel { border-right: 3px solid #38A169; }
    .fc-dxf { border-right: 3px solid #D69E2E; }
    .fc-panel { border-right: 3px solid #4A90D9; }

    /* Download card grid */
    .dl-card {
        text-align: center;
        padding: 0.6rem 0.4rem 0.3rem;
        border-radius: 10px;
        background: var(--surface);
        border: 1px solid var(--border);
        margin-bottom: 0.3rem;
    }
    .dl-card .dl-icon { font-size: 1.6rem; margin-bottom: 0.15rem; }
    .dl-card .dl-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 0.3rem;
    }

    /* Spacer utility */
    .spacer-sm { height: 0.5rem; }
    .spacer-md { height: 1rem; }
    .spacer-lg { height: 1.5rem; }

    /* Footer */
    .app-footer {
        text-align: center;
        padding: 1rem 0 0.5rem;
        font-size: 0.75rem;
        color: var(--text-muted);
        border-top: 1px solid var(--border);
        margin-top: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Element Library helpers ──────────────────────────────────────────────────

LIBRARY_FILE = Path("element_library.json")


def _load_library() -> list[dict]:
    if "element_library" not in st.session_state:
        if LIBRARY_FILE.exists():
            try:
                lib = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
                if not isinstance(lib, list):
                    lib = []
            except Exception:
                lib = []
        else:
            lib = []
        st.session_state["element_library"] = lib
    return st.session_state["element_library"]


def _save_library(lib: list[dict]):
    st.session_state["element_library"] = lib
    try:
        LIBRARY_FILE.write_text(
            json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _add_to_library(panel: dict, label: str = ""):
    lib = _load_library()
    entry = {k: v for k, v in panel.items()}
    entry["_label"] = label or panel.get("panel_id") or "element"
    entry["_saved_at"] = datetime.now().isoformat()
    lib.append(entry)
    _save_library(lib)


def _ensure_edit_data():
    if "edit_data" not in st.session_state:
        st.session_state["edit_data"] = {"header": {}, "panels": []}
        st.session_state["upload_key"] = "_manual_"


# ── Workflow state ───────────────────────────────────────────────────────────

has_data = "edit_data" in st.session_state
has_files = "generated_files" in st.session_state and st.session_state["generated_files"]

# ── Banner + Step Indicator ──────────────────────────────────────────────────

step_classes = [
    "done" if has_data else "active",
    "done" if has_data else "",
    "done" if has_files else ("active" if has_data else ""),
    "active" if has_files else "",
]

st.markdown(f"""
<div class="app-banner">
    <h1>OR Planer</h1>
    <p>תכנון הזמנות פרופילי אלומיניום</p>
    <div class="steps-bar">
        <span class="step-item {step_classes[0]}">Upload</span>
        <span class="step-arrow">&#9654;</span>
        <span class="step-item {step_classes[1]}">Edit</span>
        <span class="step-arrow">&#9654;</span>
        <span class="step-item {step_classes[2]}">Generate</span>
        <span class="step-arrow">&#9654;</span>
        <span class="step-item {step_classes[3]}">Download</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="spacer-sm"></div>', unsafe_allow_html=True)

project_id = st.text_input("מזהה פרויקט", value="GPN-1")

# ── Element Library UI ───────────────────────────────────────────────────────

st.markdown('<div class="spacer-sm"></div>', unsafe_allow_html=True)
with st.expander("📚 ספריית אלמנטים", expanded=False):
    lib = _load_library()

    if lib:
        st.markdown(f"**{len(lib)} אלמנטים שמורים**")
        for idx, elem in enumerate(lib):
            label = elem.get("_label", elem.get("panel_id", f"#{idx + 1}"))
            dims = elem.get("profile_dimensions")
            dims_str = ",".join(str(int(d)) for d in dims) if dims else "-"
            el_len = elem.get("length_mm", "-")
            el_wid = elem.get("width_mm", "-")

            c_info, c_add, c_del = st.columns([5, 2, 1])
            with c_info:
                st.caption(f"**{label}** | {el_len}x{el_wid} | {dims_str}")
            with c_add:
                if st.button("הוסף", key=f"lib_add_{idx}"):
                    _ensure_edit_data()
                    new_panel = {k: v for k, v in elem.items() if not k.startswith("_")}
                    new_panel["quantity"] = 1
                    st.session_state["edit_data"]["panels"].append(new_panel)
                    st.session_state.pop("generated_files", None)
                    st.rerun()
            with c_del:
                if st.button("✕", key=f"lib_del_{idx}"):
                    lib.pop(idx)
                    _save_library(lib)
                    st.rerun()

        if st.button("🗑️ נקה ספריה"):
            _save_library([])
            st.rerun()
    else:
        st.info("הספריה ריקה. שמור אלמנטים מהזמנות לשימוש חוזר.")

    c_exp, c_imp = st.columns(2)
    with c_exp:
        if lib:
            st.download_button(
                "ייצא ספריה",
                json.dumps(lib, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="element_library.json",
                mime="application/json",
                key="lib_export",
            )
    with c_imp:
        lib_file = st.file_uploader(
            "ייבא ספריה (JSON)", type=["json"], key="lib_import",
            label_visibility="collapsed",
        )
        if lib_file:
            try:
                imported = json.load(lib_file)
                if isinstance(imported, list):
                    current = _load_library()
                    current.extend(imported)
                    _save_library(current)
                    st.success(f"יובאו {len(imported)} אלמנטים")
                    st.rerun()
            except Exception as e:
                st.error(f"שגיאה בייבוא: {e}")

# ── File Upload Card ─────────────────────────────────────────────────────────

st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<p class="section-head">העלאת קבצים</p>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "העלאת תמונות שרטוט או JSON",
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
        st.session_state.pop("generated_files", None)

# ── Editing UI ───────────────────────────────────────────────────────────────

if "edit_data" in st.session_state:
    edit_data = st.session_state["edit_data"]

    from src.validate import validate_order_data
    valid, errors = validate_order_data(edit_data)
    if not valid:
        st.warning("מלא את השדות החסרים:")
        for e in errors:
            st.write(f"• {e}")

    # ── Header editing ──
    st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
    with st.expander("✏️ פרטי הזמנה", expanded=not valid):
        header = edit_data.get("header", {})
        header["project_id"] = st.text_input(
            "מזהה פרויקט ", value=str(header.get("project_id") or project_id))
        header["client_name"] = st.text_input(
            "שם לקוח", value=str(header.get("client_name") or ""))
        header["project_name"] = st.text_input(
            "שם פרויקט", value=str(header.get("project_name") or ""))
        header["date"] = st.text_input(
            "תאריך", value=str(header.get("date") or ""))

        c1, c2 = st.columns(2)
        with c1:
            header["color_ral"] = st.text_input(
                "צבע RAL", value=str(header.get("color_ral") or "9011"))
            header["material"] = st.text_input(
                "חומר", value=str(header.get("material") or "אלומיניום"))
        with c2:
            header["order_number"] = st.text_input(
                "מספר הזמנה", value=str(header.get("order_number") or ""))
            thick_val = header.get("thickness_mm") or 2
            thick_in = st.text_input('עובי מ"מ', value=str(int(thick_val)))
            try:
                header["thickness_mm"] = int(thick_in) if thick_in else int(thick_val)
            except ValueError:
                header["thickness_mm"] = int(thick_val)

    # ── Panel editing ──
    st.markdown('<div class="spacer-sm"></div>', unsafe_allow_html=True)
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
        else:
            st.info("אין פנלים. הוסף מהספריה או העלה קובץ.")

    # ── Summary with Metrics ─────────────────────────────────────────────────

    panels = edit_data.get("panels", [])
    if panels:
        st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<p class="section-head">סיכום הזמנה</p>', unsafe_allow_html=True)

            from src.output import get_width, panel_name
            sum_rows = []
            total_area = 0.0
            total_qty = 0
            for i, p in enumerate(panels):
                length = float(p.get("length_mm") or 0)
                width = get_width(p)
                qty = int(p.get("quantity") or 1)
                area = (length * width * qty) / 1_000_000 if width else 0
                total_area += area
                total_qty += qty
                sum_rows.append({
                    "#": i + 1,
                    "שם": panel_name(p, i),
                    "אורך": int(length),
                    "רוחב": int(width),
                    "כמות": qty,
                    'שטח מ"ר': round(area, 2),
                })

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("פנלים", len(panels))
            with m2:
                st.metric("יחידות", total_qty)
            with m3:
                st.metric('שטח מ"ר', f"{total_area:.2f}")

            st.markdown('<div class="spacer-sm"></div>', unsafe_allow_html=True)
            st.dataframe(sum_rows, use_container_width=True, hide_index=True)

    # ── Generate ─────────────────────────────────────────────────────────────

    st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
    st.markdown('<div class="generate-btn">', unsafe_allow_html=True)
    gen_clicked = st.button("צור הזמנה", type="primary")
    st.markdown('</div>', unsafe_allow_html=True)

    if gen_clicked:
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

                ts = datetime.now().strftime("%Y%m%d_%H%M")
                generated = {}
                for key, ext in [("excel", "xlsx"), ("pdf", "pdf")]:
                    p = Path(result.get(key, ""))
                    if p.exists():
                        generated[key] = {
                            "data": p.read_bytes(),
                            "name": f"{project_id}_{ts}.{ext}",
                        }

                if "dxf_zip" in result:
                    p = Path(result["dxf_zip"])
                    if p.exists():
                        generated["dxf_zip"] = {
                            "data": p.read_bytes(),
                            "name": f"DXF_{project_id}_{ts}.zip",
                        }

                if "pdf_zip" in result:
                    p = Path(result["pdf_zip"])
                    if p.exists():
                        generated["pdf_zip"] = {
                            "data": p.read_bytes(),
                            "name": f"PDF_{project_id}_{ts}.zip",
                        }

                panel_pdfs = []
                pdf_panel_dir = output_dir / "pdf_panels"
                if pdf_panel_dir.exists():
                    for pf in sorted(pdf_panel_dir.glob("*.pdf")):
                        stem = pf.stem
                        panel_pdfs.append({
                            "data": pf.read_bytes(),
                            "name": f"{stem}_{ts}.pdf",
                        })
                generated["panel_pdfs"] = panel_pdfs

                dxf_files = []
                if "dxf" in result:
                    for dxf_path_str in result["dxf"]:
                        dp = Path(dxf_path_str)
                        if dp.exists():
                            stem = dp.stem
                            dxf_files.append({
                                "data": dp.read_bytes(),
                                "name": f"{stem}_{ts}.dxf",
                                "size_kb": round(dp.stat().st_size / 1024, 1),
                            })
                generated["dxf_files"] = dxf_files

                st.session_state["generated_files"] = generated
                st.session_state["generated_pid"] = project_id
                st.session_state.pop("preview_file", None)
                st.success("הקבצים נוצרו בהצלחה!")
            except Exception as e:
                st.error(f"שגיאה: {e}")
                st.exception(e)

    # ── Generated files ──────────────────────────────────────────────────────

    if "generated_files" in st.session_state and st.session_state["generated_files"]:
        gen = st.session_state["generated_files"]
        gen_pid = st.session_state.get("generated_pid", "")

        st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<p class="section-head">הורדת קבצים</p>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if "excel" in gen:
                    st.markdown('<div class="dl-card"><div class="dl-icon">📊</div><div class="dl-label">Excel</div></div>', unsafe_allow_html=True)
                    st.download_button(
                        "📥 הורד", gen["excel"]["data"],
                        file_name=gen["excel"]["name"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_excel",
                    )
            with c2:
                if "pdf" in gen:
                    st.markdown('<div class="dl-card"><div class="dl-icon">📄</div><div class="dl-label">PDF סיכום</div></div>', unsafe_allow_html=True)
                    st.download_button(
                        "📥 הורד", gen["pdf"]["data"],
                        file_name=gen["pdf"]["name"],
                        mime="application/pdf",
                        key="dl_pdf",
                    )

            c3, c4 = st.columns(2)
            with c3:
                if "dxf_zip" in gen:
                    st.markdown('<div class="dl-card"><div class="dl-icon">📐</div><div class="dl-label">DXF (ZIP)</div></div>', unsafe_allow_html=True)
                    st.download_button(
                        "📥 הורד", gen["dxf_zip"]["data"],
                        file_name=gen["dxf_zip"]["name"],
                        mime="application/zip",
                        key="dl_dxf",
                    )
            with c4:
                if "pdf_zip" in gen:
                    st.markdown('<div class="dl-card"><div class="dl-icon">📑</div><div class="dl-label">PDF פנלים (ZIP)</div></div>', unsafe_allow_html=True)
                    st.download_button(
                        "📥 הורד", gen["pdf_zip"]["data"],
                        file_name=gen["pdf_zip"]["name"],
                        mime="application/zip",
                        key="dl_pdf_panels",
                    )

        # ── Preview section ──────────────────────────────────────────────────

        st.markdown('<div class="spacer-md"></div>', unsafe_allow_html=True)
        preview = st.session_state.get("preview_file")

        if preview is not None:
            with st.container(border=True):
                if st.button("← חזרה לרשימת הקבצים", key="preview_back"):
                    st.session_state.pop("preview_file", None)
                    st.rerun()

                ptype = preview.get("type")
                pidx = preview.get("idx", 0)

                if ptype == "summary_pdf" and "pdf" in gen:
                    st.markdown(f"**📄 {gen['pdf']['name']}**")
                    b64 = base64.b64encode(gen["pdf"]["data"]).decode()
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64}" '
                        f'width="100%" height="600" '
                        f'style="border:1px solid #ccc; border-radius:8px;">'
                        f'</iframe>',
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        "📥 הורד קובץ", gen["pdf"]["data"],
                        file_name=gen["pdf"]["name"],
                        mime="application/pdf",
                        key="dl_preview_spdf",
                    )

                elif ptype == "panel_pdf" and gen.get("panel_pdfs") and pidx < len(gen["panel_pdfs"]):
                    ppdf = gen["panel_pdfs"][pidx]
                    st.markdown(f"**📐 {ppdf['name']}**")
                    b64p = base64.b64encode(ppdf["data"]).decode()
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64p}" '
                        f'width="100%" height="600" '
                        f'style="border:1px solid #ccc; border-radius:8px;">'
                        f'</iframe>',
                        unsafe_allow_html=True,
                    )
                    nav_cols = st.columns(3)
                    total = len(gen["panel_pdfs"])
                    with nav_cols[0]:
                        if pidx > 0:
                            if st.button("→ הקודם", key="preview_prev"):
                                st.session_state["preview_file"] = {"type": "panel_pdf", "idx": pidx - 1}
                                st.rerun()
                    with nav_cols[1]:
                        st.caption(f"{pidx + 1} / {total}")
                    with nav_cols[2]:
                        if pidx < total - 1:
                            if st.button("← הבא", key="preview_next"):
                                st.session_state["preview_file"] = {"type": "panel_pdf", "idx": pidx + 1}
                                st.rerun()
                    st.download_button(
                        f"📥 {ppdf['name']}", ppdf["data"],
                        file_name=ppdf["name"],
                        mime="application/pdf",
                        key="dl_preview_ppdf",
                    )

                elif ptype == "excel" and "excel" in gen:
                    st.markdown(f"**📊 {gen['excel']['name']}**")
                    try:
                        import io
                        excel_df = pd.read_excel(
                            io.BytesIO(gen["excel"]["data"]), header=4,
                        )
                        st.dataframe(excel_df, use_container_width=True, hide_index=True)
                    except Exception:
                        st.info("לא ניתן להציג. הורד את הקובץ.")
                    st.download_button(
                        "📥 הורד קובץ", gen["excel"]["data"],
                        file_name=gen["excel"]["name"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_preview_xl",
                    )

                st.caption("אם התצוגה ריקה במובייל, השתמש בכפתור ההורדה")

        else:
            with st.container(border=True):
                st.markdown('<p class="section-head">תצוגה מקדימה</p>', unsafe_allow_html=True)

                if "excel" in gen:
                    if st.button("📊  Excel — טבלת הזמנה", key="pv_excel"):
                        st.session_state["preview_file"] = {"type": "excel"}
                        st.rerun()

                if "pdf" in gen:
                    if st.button("📄  PDF — סיכום הזמנה", key="pv_spdf"):
                        st.session_state["preview_file"] = {"type": "summary_pdf"}
                        st.rerun()

                if gen.get("panel_pdfs"):
                    st.markdown(f'<p class="section-head" style="margin-top:0.6rem">PDF פנלים ({len(gen["panel_pdfs"])})</p>', unsafe_allow_html=True)
                    for pidx, ppdf in enumerate(gen["panel_pdfs"]):
                        if st.button(f"📐  {ppdf['name']}", key=f"pv_ppdf_{pidx}"):
                            st.session_state["preview_file"] = {"type": "panel_pdf", "idx": pidx}
                            st.rerun()

                if gen.get("dxf_files"):
                    st.markdown(f'<p class="section-head" style="margin-top:0.6rem">DXF ({len(gen["dxf_files"])})</p>', unsafe_allow_html=True)
                    for didx, dfile in enumerate(gen["dxf_files"]):
                        ci, cd = st.columns([3, 1])
                        with ci:
                            st.markdown(f"📏 **{dfile['name']}** — {dfile['size_kb']} KB")
                        with cd:
                            st.download_button(
                                "📥", dfile["data"],
                                file_name=dfile["name"],
                                mime="application/dxf",
                                key=f"dl_dxf_{didx}",
                            )

        # ── Save to Library ──────────────────────────────────────────────────

        panels = edit_data.get("panels", [])
        if panels:
            st.markdown('<div class="spacer-sm"></div>', unsafe_allow_html=True)
            with st.expander("💾 שמור אלמנטים לספריה"):
                st.caption("שמור פנלים כתבניות לשימוש חוזר בהזמנות עתידיות")
                from src.output import panel_name as _pn
                for i, p in enumerate(panels):
                    name = _pn(p, i)
                    dims = p.get("profile_dimensions")
                    dims_str = ",".join(str(int(d)) for d in dims) if dims else "-"
                    ci, cb = st.columns([4, 1])
                    with ci:
                        st.caption(f"**{name}** | פרופיל: {dims_str}")
                    with cb:
                        if st.button("שמור", key=f"save_lib_{i}"):
                            _add_to_library(p, name)
                            st.success(f"נשמר: {name}")
                            st.rerun()

                if len(panels) > 1:
                    if st.button("💾 שמור הכל לספריה"):
                        for i, p in enumerate(panels):
                            _add_to_library(p, _pn(p, i))
                        st.success(f"נשמרו {len(panels)} אלמנטים לספריה")
                        st.rerun()

else:
    st.markdown('<div class="spacer-lg"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            '<div style="text-align:center; padding:1.5rem 0.5rem;">'
            '<p style="font-size:2rem; margin-bottom:0.3rem;">📐</p>'
            '<p style="font-weight:600; color:#4A5568; margin-bottom:0.3rem;">מוכן להתחיל</p>'
            '<p style="font-size:0.85rem; color:#718096;">'
            'העלה תמונות שרטוט או קובץ JSON, או הוסף אלמנטים מהספריה'
            '</p></div>',
            unsafe_allow_html=True,
        )

# ── Footer ───────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="app-footer">OR Planer v2.0 &nbsp;&middot;&nbsp; Salvado Yafo</div>',
    unsafe_allow_html=True,
)
