"""
흡광도 분석 엔진.
1. BL 평균 차감
2. 샘플별 replicate 평균
3. NC(Negative Control) 기준 % 변환
4. 통계 (Mean, SD, T-test vs Reference 1st & 2nd)
5. PC(Positive Control) 지원
"""
import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit as scipy_curve_fit
from utils import natural_sort_key


# ── 4PL Model Functions ──
def logistic4(x, A, B, C, D):
    """4-Parameter Logistic equation."""
    return ((A - D) / (1.0 + ((x / C) ** B))) + D


def solve_4pl(y, A, B, C, D):
    """Inverse 4PL: calculate concentration from absorbance."""
    ratio = (A - D) / (y - D) - 1.0
    if ratio <= 0:
        return 0.0
    return C * (ratio ** (1.0 / B))


def run_analysis(plate_df, well_map, assay_type="Cell Viability", ref_1st=None, ref_2nd=None,
                 custom_names=None, excluded_wells=None, st_concs=None, curve_fit="Linear"):
    """
    Parameters
    ----------
    plate_df : pd.DataFrame (8×12)
    well_map : dict  {"A1": {"type": "BL"}, ...}
    assay_type : str ("Cell Viability", "DPPH", "ELISA", "Fluorescence")
    ref_1st  : str   1st reference 라벨 (NC, fold change 기준)
    ref_2nd  : str   2nd reference 라벨 (optional, 추가 t-test 비교 대상)
    custom_names : dict  {"SM1": "Vehicle", ...}
    excluded_wells : set of well_ids to ignore
    st_concs : dict {"ST1": 3200, ...} for ELISA

    Returns
    -------
    dict with keys: stats_df, processed_df, ref_1st, ref_2nd, custom_names, elisa_curve, ...
    """
    if custom_names is None:
        custom_names = {}
    if excluded_wells is None:
        excluded_wells = set()
    else:
        excluded_wells = set(excluded_wells)
    if st_concs is None:
        st_concs = {}

    rows_map = {r: i for i, r in enumerate("ABCDEFGH")}
    cols_map = {str(c): c - 1 for c in range(1, 13)}

    def _get_value(well_id):
        row_letter = well_id[0].upper()
        col_num = well_id[1:]
        ri = rows_map.get(row_letter)
        ci = cols_map.get(col_num)
        if ri is None or ci is None:
            return np.nan
        try:
            val = plate_df.iloc[ri, ci]
            return float(val) if pd.notna(val) else np.nan
        except (IndexError, ValueError, TypeError):
            return np.nan

    # ── 1. Blank 평균 계산 (excluded 제외) ──
    bl_values = [
        _get_value(wid) for wid, info in well_map.items()
        if info["type"] == "BL" and wid not in excluded_wells
    ]
    bl_mean = float(np.nanmean(bl_values)) if bl_values else 0.0

    if assay_type == "DPPH":
        bl_mean = 0.0

    # ── 2. 각 웰에서 BL 차감 & 샘플별 그룹핑 (excluded 제외) ──
    sample_data = {}  # {"SM1": [val1, val2, ...], ...}
    processed_records = []

    for wid, info in well_map.items():
        if wid in excluded_wells:
            continue
        
        label = info.get("label", info["type"])
        raw_val = _get_value(wid)
        corrected = raw_val - bl_mean
        
        processed_records.append({
            "Well": wid,
            "Type": info["type"],
            "Label": label,
            "Raw": raw_val,
            "BL_corrected": corrected,
            "Excluded": False
        })
        
        if info["type"] == "BL":
            continue
            
        sample_data.setdefault(label, []).append(corrected)

    # ── 3. Assay-specific Calculation ──
    sample_pct = {}
    elisa_curve = None

    if assay_type == "Cell Viability":
        if ref_1st and ref_1st in sample_data:
            nc_mean = np.nanmean(sample_data[ref_1st])
        else:
            nc_values = [v for l, vs in sample_data.items() if l.startswith("NC") for v in vs]
            nc_mean = np.nanmean(nc_values) if nc_values else 1.0
            if ref_1st is None:
                nc_labels = [l for l in sample_data.keys() if l.startswith("NC")]
                if nc_labels: ref_1st = nc_labels[0]

        if nc_mean == 0: nc_mean = 1e-10

        for rec in processed_records:
            if rec["Type"] == "BL":
                rec["Value"] = 0
            else:
                rec["Value"] = (rec["BL_corrected"] / nc_mean) * 100
            
            if rec["Type"] != "BL":
                sample_pct.setdefault(rec["Label"], []).append(rec["Value"])

    elif assay_type == "DPPH":
        if ref_1st and ref_1st in sample_data:
            nc_mean = np.mean(sample_data[ref_1st])
        else:
            nc_values = [v for l, vs in sample_data.items() if l.startswith("NC") for v in vs]
            nc_mean = np.mean(nc_values) if nc_values else 1.0
            if ref_1st is None:
                nc_labels = [l for l in sample_data.keys() if l.startswith("NC")]
                if nc_labels: ref_1st = nc_labels[0]
                
        if nc_mean == 0: nc_mean = 1e-10
        
        for rec in processed_records:
            if rec["Type"] == "BL":
                rec["Value"] = 0
            else:
                rec["Value"] = (1 - (rec["BL_corrected"] / nc_mean)) * 100
                
            if rec["Type"] != "BL":
                sample_pct.setdefault(rec["Label"], []).append(rec["Value"])
                
    elif assay_type in ["ELISA", "Fluorescence"]:
        st_groups = {}
        for rec in processed_records:
            label = rec["Label"]
            if rec["Type"] == "ST" and label in st_concs and pd.notna(rec["BL_corrected"]):
                val = rec["BL_corrected"]
                st_groups.setdefault(label, []).append(val)
                
        st_x = []
        st_y = []
        for label, vals in st_groups.items():
            mean_val = float(np.nanmean(vals))
            st_x.append(st_concs[label])
            st_y.append(mean_val)
        
        if len(st_x) > 1:
            if curve_fit == "4PL":
                # ── 4-Parameter Logistic Regression ──
                st_x_arr = np.array(st_x, dtype=float)
                st_y_arr = np.array(st_y, dtype=float)
                try:
                    # Initial guesses: A=min(y), B=1, C=median(x), D=max(y)
                    p0 = [min(st_y_arr), 1.0, np.median(st_x_arr), max(st_y_arr)]
                    popt, _ = scipy_curve_fit(logistic4, st_x_arr, st_y_arr, p0=p0, maxfev=10000)
                    A, B, C, D = popt
                    
                    # R² calculation
                    y_pred = logistic4(st_x_arr, *popt)
                    ss_res = np.sum((st_y_arr - y_pred) ** 2)
                    ss_tot = np.sum((st_y_arr - np.mean(st_y_arr)) ** 2)
                    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
                    
                    elisa_curve = {
                        "curve_fit": "4PL",
                        "A": float(A),
                        "B": float(B),
                        "C": float(C),
                        "D": float(D),
                        "r_squared": r_squared,
                        "equation": f"y = ({A:.4f} - {D:.4f}) / (1 + (x/{C:.4f})^{B:.4f}) + {D:.4f}",
                        "warning": r_squared < 0.95
                    }
                    def _calc_conc(abs_val, _A=A, _B=B, _C=C, _D=D):
                        try:
                            return max(0.0, solve_4pl(abs_val, _A, _B, _C, _D))
                        except Exception:
                            return 0.0
                except Exception as e:
                    elisa_curve = {"warning": True, "error": f"4PL fitting failed: {e}"}
                    def _calc_conc(abs_val): return 0.0
            else:
                # ── Linear Regression (default for Fluorescence) ──
                slope, intercept, r_value, p_value, std_err = stats.linregress(st_x, st_y)
                r_squared = r_value**2
                elisa_curve = {
                    "curve_fit": "Linear",
                    "slope": slope,
                    "intercept": intercept,
                    "r_squared": r_squared,
                    "equation": f"y = {slope:.4e}x + {intercept:.4f}",
                    "inverse_eq": f"x = (y - {intercept:.4f}) / {slope:.4e}",
                    "warning": r_squared < 0.95
                }
                def _calc_conc(abs_val):
                    if slope == 0: return 0.0
                    conc = (abs_val - intercept) / slope
                    return max(0.0, conc)
        else:
            elisa_curve = {"warning": True, "error": "Not enough ST points for regression"}
            def _calc_conc(abs_val): return 0.0
            
        for rec in processed_records:
            if rec["Type"] == "BL":
                rec["Value"] = 0
            else:
                rec["Value"] = _calc_conc(rec["BL_corrected"])
                
            if rec["Type"] not in ["BL", "ST"]:
                sample_pct.setdefault(rec["Label"], []).append(rec["Value"])

    # Excluded wells also need to be logged (mostly for UI display)
    for wid, info in well_map.items():
        if wid in excluded_wells:
            raw_val = _get_value(wid)
            processed_records.append({
                "Well": wid,
                "Type": info["type"],
                "Label": info.get("label", info["type"]),
                "Raw": raw_val,
                "BL_corrected": np.nan,
                "Excluded": True,
                "Value": np.nan
            })

    processed_df = pd.DataFrame(processed_records)

    # ── 4. 통계 계산 ──
    ref1_pct = sample_pct.get(ref_1st, [100])
    ref2_pct = sample_pct.get(ref_2nd, []) if ref_2nd else []

    stat_rows = []
    for label in sorted(sample_pct.keys(), key=natural_sort_key):
        values = sample_pct[label]
        clean_values = [v for v in values if pd.notna(v)]
        mean_val = np.nanmean(values) if clean_values else 0.0
        sd_val = np.nanstd(values, ddof=1) if len(clean_values) > 1 else 0.0
        n = len(clean_values)

        # T-test vs ref_1st
        if label == ref_1st:
            p_val_1 = np.nan
            sig_1 = "-"
        else:
            ref1_clean = [v for v in ref1_pct if pd.notna(v)]
            if len(clean_values) >= 2 and len(ref1_clean) >= 2:
                if np.var(clean_values) == 0 and np.var(ref1_clean) == 0:
                    p_val_1 = np.nan
                else:
                    _, p_val_1 = stats.ttest_ind(clean_values, ref1_clean, equal_var=False)
            else:
                p_val_1 = np.nan
            sig_1 = _significance(p_val_1)

        # T-test vs ref_2nd
        p_val_2 = np.nan
        sig_2 = "-"
        if ref_2nd and ref2_pct:
            if label == ref_2nd:
                p_val_2 = np.nan
                sig_2 = "-"
            else:
                ref2_clean = [v for v in ref2_pct if pd.notna(v)]
                if len(clean_values) >= 2 and len(ref2_clean) >= 2:
                    if np.var(clean_values) == 0 and np.var(ref2_clean) == 0:
                        p_val_2 = np.nan
                    else:
                        _, p_val_2 = stats.ttest_ind(clean_values, ref2_clean, equal_var=False)
                sig_2 = _significance(p_val_2)

        display_name = custom_names.get(label, label)

        row_data = {
            "Label": label,
            "Display Name": display_name,
            "N": n,
            "Mean_Value": mean_val,
            "SD_Value": sd_val,
            f"p vs {custom_names.get(ref_1st, ref_1st) if ref_1st else 'Ref1'}": p_val_1,
            f"Sig vs {custom_names.get(ref_1st, ref_1st) if ref_1st else 'Ref1'}": sig_1,
        }

        if ref_2nd and ref2_pct:
            ref2_display = custom_names.get(ref_2nd, ref_2nd)
            row_data[f"p vs {ref2_display}"] = p_val_2
            row_data[f"Sig vs {ref2_display}"] = sig_2

        stat_rows.append(row_data)

    stats_df = pd.DataFrame(stat_rows)

    return {
        "assay_type": assay_type,
        "stats_df": stats_df,
        "processed_df": processed_df,
        "sample_pct": sample_pct,
        "ref_1st": ref_1st,
        "ref_2nd": ref_2nd,
        "custom_names": custom_names,
        "bl_mean": bl_mean,
        "elisa_curve": elisa_curve,
        "st_concs": st_concs
    }


def qc_check(plate_df, well_map, sd_threshold=0.5):
    """
    Quality Control: 각 그룹의 raw absorbance SD를 계산하고
    SD > threshold인 그룹과 개별 웰 값을 반환.

    Returns
    -------
    list of dict:
        [{"label": "SM1", "wells": [{"well": "A3", "value": 1.95}, ...],
          "mean": 1.90, "sd": 0.55, "flagged": True}, ...]
    """
    rows_map = {r: i for i, r in enumerate("ABCDEFGH")}
    cols_map = {str(c): c - 1 for c in range(1, 13)}

    def _get_value(well_id):
        row_letter = well_id[0].upper()
        col_num = well_id[1:]
        try:
            val = plate_df.iloc[rows_map[row_letter], cols_map[col_num]]
            return float(val) if pd.notna(val) else np.nan
        except (KeyError, IndexError, ValueError, TypeError):
            return np.nan

    # 그룹별 웰 & 값 수집
    groups = {}  # label -> [{"well": "A3", "value": 1.95}, ...]
    for wid, info in well_map.items():
        label = info.get("label", info["type"])
        val = _get_value(wid)
        groups.setdefault(label, []).append({"well": wid, "value": val})

    result = []
    for label in sorted(groups.keys(), key=natural_sort_key):
        wells = groups[label]
        values = [w["value"] for w in wells]
        clean_vals = [v for v in values if pd.notna(v)]
        mean_val = float(np.nanmean(values)) if clean_vals else 0.0
        sd_val = float(np.nanstd(values, ddof=1)) if len(clean_vals) > 1 else 0.0
        cv_val = float((sd_val / mean_val) * 100) if mean_val != 0 else 0.0
        
        result.append({
            "label": label,
            "wells": sorted(wells, key=lambda w: w["well"]),
            "mean": mean_val,
            "sd": sd_val,
            "cv": cv_val,
            "flagged": cv_val >= 5,
        })

    return result


def _significance(p):
    if pd.isna(p):
        return "-"
    if p < 0.001:
        return "***"
    elif p < 0.01:
        return "**"
    elif p < 0.05:
        return "*"
    else:
        return "ns"
