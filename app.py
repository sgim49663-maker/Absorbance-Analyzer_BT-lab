import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import json
import os

from utils import natural_sort_key
from utils.csv_parser import parse_plate_csv
from utils.analysis import run_analysis, qc_check
from utils.visualization import create_bar_chart, create_elisa_curve_chart
from utils.export_excel import generate_excel
from utils.export_pptx import generate_pptx

# ============================================================
# Drag selection component
# ============================================================
COMPONENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "plate_grid")
plate_grid = components.declare_component("plate_grid", path=COMPONENT_DIR)

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="Absorbance Analyzer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #4A90D9 0%, #7B68EE 100%);
        padding: 1.5rem 2rem; border-radius: 12px;
        margin-bottom: 1.5rem; color: white;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p { color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .desc-box { font-family: 'Georgia', serif; font-size: 1.1rem; color: #333; background: #f9f9f9; padding: 1rem; border-left: 4px solid #4A90D9; margin-bottom: 1rem;}
    .stButton > button { border-radius: 8px; font-weight: 600; transition: all 0.2s; }
    div[data-testid="stSidebar"] { background: #F7F8FC; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Session State Init
# ============================================================
defaults = {
    "plates": {},
    "current_plate": None,
    "well_maps": {},
    "analysis_results": {},
    "current_tool": "BL",
    "custom_sample_names": {},
    "ref_1st_labels": {},       
    "ref_2nd_labels": {},       
    "excluded_wells": {},       
    "last_selection_ts": None,
    "active_assay": "Cell Viability",
    "elisa_st_concs": {},
    "current_st_choice": "ST1"
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# Header & Assay Selection
# ============================================================
st.markdown("""
<div class="main-header">
    <h1>🧬 Absorbance Analyzer</h1>
    <p>Data Upload → Plate Mapping → Quality Check → Analysis → Export</p>
</div>
""", unsafe_allow_html=True)

assay_type = st.radio(
    "Select Assay Type", 
    options=["Cell Viability", "DPPH", "ELISA", "Fluorescence"],
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state.active_assay = assay_type

if assay_type in ["Cell Viability"]:
    st.markdown("""<div class="desc-box" style="font-size: 0.9rem;">
    <b>Wavelength:</b> 450nm<br/>
    <b>Calculation:</b> <code>Cell Viability (%) = (Sample - Blank) / (Control - Blank) × 100</code>
    </div>""", unsafe_allow_html=True)
elif assay_type == "DPPH":
    st.markdown("""<div class="desc-box" style="font-size: 0.9rem;">
    <b>Calculation:</b> <code>Scavenging Activity (%) = (1 - Sample / Control) × 100</code>
    </div>""", unsafe_allow_html=True)
elif assay_type in ["ELISA", "Fluorescence"]:
    if assay_type == "ELISA":
        st.markdown("""<div class="desc-box" style="font-size: 0.9rem;">
        <b>Calculation:</b> 4-Parameter Logistic (4PL) Standard Curve fitting with ST → Calculate Concentration.<br/>
        Fits Sample values to the generated Standard Curve using <code>y = (A-D)/(1+(x/C)^B) + D</code>.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="desc-box" style="font-size: 0.9rem;">
        <b>Calculation:</b> Draw standard regression curve with ST → Calculate Concentration based on formula.<br/>
        Fits Sample values to the generated Standard Curve.
        </div>""", unsafe_allow_html=True)

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.header("📂 1. Data Upload")
    uploaded = st.file_uploader(
        "Upload CSV",
        type=["csv", "txt"],
    )
    if uploaded:
        try:
            plates = parse_plate_csv(uploaded)
            st.session_state.plates = plates
            for pname in plates:
                if pname not in st.session_state.well_maps:
                    st.session_state.well_maps[pname] = {}
                if pname not in st.session_state.excluded_wells:
                    st.session_state.excluded_wells[pname] = set()
            if st.session_state.current_plate not in plates:
                st.session_state.current_plate = list(plates.keys())[0]
            st.success(f"✅ {len(plates)} plates loaded")
        except Exception as e:
            st.error(f"CSV Parse Error: {e}")

    st.markdown("---")

    if len(st.session_state.plates) > 1:
        st.header("🔀 Plate Selection")
        pkeys = list(st.session_state.plates.keys())
        plate_choice = st.radio(
            "Select Plate",
            options=pkeys,
            index=pkeys.index(st.session_state.current_plate)
            if st.session_state.current_plate in pkeys else 0,
            horizontal=True,
        )
        st.session_state.current_plate = plate_choice
        st.markdown("---")

    if st.session_state.current_plate:
        st.header("💾 Load / Save Layout")
        
        mapping_data = {
            "well_maps": st.session_state.well_maps.get(st.session_state.current_plate, {}),
            "custom_sample_names": st.session_state.custom_sample_names,
            "excluded_wells": list(st.session_state.excluded_wells.get(st.session_state.current_plate, set())),
            "elisa_st_concs": st.session_state.get("elisa_st_concs", {})
        }
        st.download_button(
            "📥 Export Mapping as JSON",
            data=json.dumps(mapping_data, indent=2),
            file_name="plate_layout.json",
            mime="application/json",
            use_container_width=True
        )
        
        uploaded_layout = st.file_uploader("📤 Upload Mapping JSON", type=["json"])
        if uploaded_layout is not None:
            if st.button("Apply Uploaded Layout", type="primary", use_container_width=True):
                try:
                    layout_dict = json.load(uploaded_layout)
                    st.session_state.well_maps[st.session_state.current_plate] = layout_dict.get("well_maps", {})
                    st.session_state.custom_sample_names = layout_dict.get("custom_sample_names", {})
                    st.session_state.excluded_wells[st.session_state.current_plate] = set(layout_dict.get("excluded_wells", []))
                    if "elisa_st_concs" in layout_dict:
                        st.session_state.elisa_st_concs = layout_dict["elisa_st_concs"]
                    st.success("레이아웃이 성공적으로 적용되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error("JSON 파일을 읽는 데 실패했습니다.")
        st.markdown("---")

    st.header("🎨 2. Mapping Tool")
    
    if assay_type == "DPPH":
        tool_options = ["NC (Neg. Ctrl)", "PC (Pos. Ctrl)", "SM (Sample)", "Clear"]
    elif assay_type in ["ELISA", "Fluorescence"]:
        tool_options = ["BL (Blank)", "ST (Standard)", "NC (Neg. Ctrl)", "PC (Pos. Ctrl)", "SM (Sample)", "Clear"]
        st.subheader("ST Configuration")
        st_count = st.number_input("Number of STs", min_value=1, max_value=20, value=8)
        st_start = st.number_input("Start Conc (ST1)", value=3200.0)
        st_end = st.number_input("End Conc", value=0.0)
        st_fold = st.number_input("Fold Dilution", value=2.0)
        if st.button("Generate STs"):
            concs = {}
            cur_conc = st_start
            for i in range(1, st_count + 1):
                if i == st_count:
                    concs[f"ST{i}"] = st_end
                else:
                    concs[f"ST{i}"] = cur_conc
                    cur_conc = cur_conc / st_fold
            st.session_state.elisa_st_concs = concs
            st.success("STs generated!")
        
        # Curve Fit Method: ELISA = 4PL only, Fluorescence = Linear / 4PL
        if assay_type == "ELISA":
            st.info("📐 Curve Fit: **4PL** (4-Parameter Logistic)")
            st.session_state.current_curve_fit = "4PL"
        else:
            curve_fit = st.selectbox("Curve Fit Method", ["Linear", "4PL"], index=0)
            st.session_state.current_curve_fit = curve_fit
        
    else:
        tool_options = ["BL (Blank)", "NC (Neg. Ctrl)", "PC (Pos. Ctrl)", "SM (Sample)", "Clear"]

    tool = st.radio(
        "Select well type & drag on grid",
        options=tool_options,
        index=0
    )
    tool_key = tool.split(" ")[0]
    st.session_state.current_tool = tool_key

    if tool_key == "ST" and assay_type in ["ELISA", "Fluorescence"]:
        st_choice = st.selectbox("Select ST to Map", options=list(st.session_state.elisa_st_concs.keys()) if st.session_state.elisa_st_concs else ["ST1"])
        st.session_state.current_st_choice = st_choice

    if tool_key in ("SM", "NC", "PC"):
        sm_num = st.number_input("Number", 1, 96, 1, key="sm_num")

    st.markdown("---")

    cur_plate = st.session_state.current_plate
    cur_wm = st.session_state.well_maps.get(cur_plate, {})
    mapped_labels = sorted(set(
        v.get("label", v["type"]) for v in cur_wm.values() if v.get("type") not in ("BL",)
    ), key=natural_sort_key)

    if mapped_labels:
        with st.expander("✏️ Sample Name Config", expanded=False):
            for label in mapped_labels:
                # Set defaults based on assay
                default_val = st.session_state.custom_sample_names.get(label, "")
                help_txt = ""

                if label.startswith("NC"):
                    if not default_val: default_val = "None"
                elif label.startswith("PC"):
                    if not default_val:
                        if assay_type in ["Cell Viability", "Fluorescence"]:
                            default_val = "hEGF"
                        elif assay_type == "DPPH":
                            default_val = "Ascorbic Acid"

                if assay_type == "DPPH" and label.startswith("PC"):
                    help_txt = "e.g., AA 0.1% or AA 0.01%"

                new_name = st.text_input(
                    label,
                    value=default_val,
                    key=f"name_{cur_plate}_{label}",
                    help=help_txt
                )
                if new_name:
                    st.session_state.custom_sample_names[label] = new_name
                elif label in st.session_state.custom_sample_names:
                    del st.session_state.custom_sample_names[label]

        st.header("📐 3. Reference Config")
        nc_labels = [l for l in mapped_labels if l.startswith("NC")]
        default_1st = nc_labels[0] if nc_labels else mapped_labels[0]
        default_1st_idx = mapped_labels.index(default_1st) if default_1st in mapped_labels else 0

        ref1 = st.selectbox(
            "1st Reference (Control)",
            options=mapped_labels,
            index=default_1st_idx,
            key=f"ref1_{cur_plate}"
        )
        st.session_state.ref_1st_labels[cur_plate] = ref1

        ref2_options = ["(None)"] + [l for l in mapped_labels if l != ref1]
        ref2 = st.selectbox(
            "2nd Reference (for t-test)",
            options=ref2_options,
            index=0,
            key=f"ref2_{cur_plate}"
        )
        st.session_state.ref_2nd_labels[cur_plate] = ref2 if ref2 != "(None)" else None
    
    st.markdown("---")
    analyze_btn = st.button("🚀 Run Analysis", use_container_width=True, type="primary")


# ============================================================
# Main View: Plate & Results
# ============================================================
if st.session_state.plates:
    plate_df = st.session_state.plates[cur_plate]
    
    tab_plate, tab_qc, tab_result = st.tabs(["🧫 Plate Mapping", "✅ Quality Check", "📊 Results"])

    with tab_plate:
        st.subheader("Plate Mapping")
        selection = plate_grid(
            plate_values=plate_df.values.tolist(),
            well_map=cur_wm,
            key=f"grid_{cur_plate}",
        )

        if selection is not None:
            sel_ts = selection.get("ts")
            sel_wells = selection.get("wells", [])
            if sel_ts and sel_ts != st.session_state.last_selection_ts and sel_wells:
                st.session_state.last_selection_ts = sel_ts
                tool_k = st.session_state.current_tool
                for well_id in sel_wells:
                    if tool_k == "Clear":
                        cur_wm.pop(well_id, None)
                    elif tool_k == "BL":
                        cur_wm[well_id] = {"type": "BL"}
                    elif tool_k == "ST":
                        c_st = st.session_state.get("current_st_choice", "ST1")
                        cur_wm[well_id] = {"type": "ST", "label": c_st}
                    elif tool_k in ("SM", "NC", "PC"):
                        num = st.session_state.get("sm_num", 1)
                        cur_wm[well_id] = {"type": tool_k, "label": f"{tool_k}{num}"}
                st.rerun()

        st.markdown("##### 📋 Mapping Summary")
        summary = {}
        for wid, info in cur_wm.items():
            key = info.get("label", info["type"])
            summary.setdefault(key, []).append(wid)
        for k in sorted(summary.keys(), key=natural_sort_key):
            wells = ", ".join(sorted(summary[k]))
            d_name = st.session_state.custom_sample_names.get(k, k)
            st.write(f"**{k}** ({d_name}): {wells} ({len(summary[k])} wells)")

    with tab_qc:
        st.subheader("🧪 Quality Check")
        st.caption("Check for well variability before final analysis.")
        
        qc_results = qc_check(plate_df, cur_wm, sd_threshold=0.5)
        new_excluded = set(st.session_state.excluded_wells.get(cur_plate, set()))
        
        for res_q in qc_results:
            cv = res_q.get("cv", 0.0)
            msg = f"**{res_q['label']}** - CV: {cv:.1f}%"
            
            if cv >= 20:
                st.markdown(f'<div style="background-color: #FFCDD2; padding: 10px; border-radius: 5px; color: #B71C1C; margin-bottom: 10px;">🔴 {msg}</div>', unsafe_allow_html=True)
            elif cv >= 10:
                st.markdown(f'<div style="background-color: #FFE0B2; padding: 10px; border-radius: 5px; color: #E65100; margin-bottom: 10px;">🟠 {msg}</div>', unsafe_allow_html=True)
            elif cv >= 5:
                st.markdown(f'<div style="background-color: #FFF9C4; padding: 10px; border-radius: 5px; color: #F57F17; margin-bottom: 10px;">🟡 {msg}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="background-color: #C8E6C9; padding: 10px; border-radius: 5px; color: #1B5E20; margin-bottom: 10px;">🟢 {msg} (Good)</div>', unsafe_allow_html=True)
                
                
            cols = st.columns(min(8, max(1, len(res_q["wells"]))))
            for idx, w in enumerate(res_q["wells"]):
                c_idx = idx % len(cols)
                with cols[c_idx]:
                    wid = w["well"]
                    val = w["value"]
                    is_ex = wid in new_excluded
                    if st.checkbox(f"**{wid}**\n{val:.3f}", value=is_ex, key=f"qc_{cur_plate}_{wid}"):
                        new_excluded.add(wid)
                    else:
                        new_excluded.discard(wid)
                        
        if st.button("Apply QC Changes", type="secondary"):
            st.session_state.excluded_wells[cur_plate] = new_excluded
            st.success("Excluded wells saved. You can now press [Run Analysis].")

    if analyze_btn:
        with st.spinner("Analyzing..."):
            try:
                result = run_analysis(
                    plate_df=plate_df,
                    well_map=cur_wm,
                    assay_type=assay_type,
                    ref_1st=st.session_state.ref_1st_labels.get(cur_plate),
                    ref_2nd=st.session_state.ref_2nd_labels.get(cur_plate),
                    custom_names=st.session_state.custom_sample_names,
                    excluded_wells=st.session_state.excluded_wells.get(cur_plate, set()),
                    st_concs=st.session_state.elisa_st_concs,
                    curve_fit=st.session_state.get("current_curve_fit", "Linear")
                )
                st.session_state.analysis_results[cur_plate] = result
                st.success("✅ Analysis Complete!")
            except Exception as e:
                st.error(f"Analysis Error: {e}")

    with tab_result:
        res = st.session_state.analysis_results.get(cur_plate)
        if res:
            st.subheader("📊 Analysis Results")
            if assay_type in ["ELISA", "Fluorescence"] and res.get("elisa_curve"):
                c_data = res["elisa_curve"]
                if c_data.get("warning"):
                    st.warning(f"⚠️ R² is below 0.95! Current R²: {c_data.get('r_squared', 0):.4f}")
                    
            st.markdown("##### Statistics Table")
            st.dataframe(res["stats_df"], use_container_width=True)

            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("##### Bar Chart")
                fig_bar = create_bar_chart(res)
                st.pyplot(fig_bar)
            
            if assay_type in ["ELISA", "Fluorescence"] and res.get("elisa_curve") and "error" not in res["elisa_curve"]:
                with col2:
                    st.markdown("##### Standard Curve")
                    fig_curve = create_elisa_curve_chart(res["elisa_curve"], res["st_concs"], res["processed_df"])
                    st.pyplot(fig_curve)

            with st.expander("📄 Processed Data"):
                st.dataframe(res["processed_df"], use_container_width=True)

            st.markdown("##### 📥 Export")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                excel_bytes = generate_excel(res)
                st.download_button("📗 Download Excel", data=excel_bytes, file_name=f"analysis_{cur_plate}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_d2:
                pptx_bytes = generate_pptx(res)
                st.download_button("📙 Download PPTX", data=pptx_bytes, file_name=f"analysis_{cur_plate}.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)

else:
    st.info("Upload CSV on the sidebar to begin.")


