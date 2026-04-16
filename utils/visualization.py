"""
분석 결과 바 차트 생성 (matplotlib).
- 깔끔한 논문 스타일
- NC=흰색, PC=회색, SM=연녹색
- significance bracket + 별표
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from utils import natural_sort_key


def create_bar_chart(result: dict, figsize=(5, 4)):
    """컴팩트한 논문 스타일 바 차트."""
    stats_df = result["stats_df"].copy()
    ref_1st = result.get("ref_1st")
    ref_2nd = result.get("ref_2nd")
    custom_names = result.get("custom_names", {})
    assay_type = result.get("assay_type", "Cell Viability")

    # 정렬: ref_1st 맨 앞, ref_2nd 그 다음, 나머지는 자연수 정렬
    order_labels = []
    if ref_1st and ref_1st in stats_df["Label"].values:
        order_labels.append(ref_1st)
    if ref_2nd and ref_2nd in stats_df["Label"].values and ref_2nd not in order_labels:
        order_labels.append(ref_2nd)
    remaining = sorted(
        [lab for lab in stats_df["Label"].unique() if lab not in order_labels],
        key=natural_sort_key,
    )
    order_labels.extend(remaining)

    stats_df["_order"] = stats_df["Label"].apply(lambda x: order_labels.index(x) if x in order_labels else 999)
    stats_df = stats_df.sort_values("_order").reset_index(drop=True)

    labels_raw = stats_df["Label"].tolist()
    display_names = [custom_names.get(lab, lab) for lab in labels_raw]
    means = stats_df["Mean_Value"].values
    sds = stats_df["SD_Value"].values

    # ── 색상: 모두 흰색 ──
    palette = ["#FFFFFF"] * len(labels_raw)
    edge_colors = ["#000000"] * len(labels_raw)

    # ── 폰트 & 스타일 ──
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
    })

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(display_names))
    bar_width = 0.55

    # 양방향 에러바
    bars = ax.bar(
        x, means, width=bar_width, yerr=sds,
        color=palette, edgecolor=edge_colors, linewidth=0.8,
        capsize=3,
        error_kw={"elinewidth": 0.8, "capthick": 0.8, "color": "#000"},
        zorder=3,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(display_names, rotation=0, ha="center", fontsize=8) # 기울임 0도
    
    # Y-axis title based on assay_type
    y_label = "Relative Absorbance (%)"
    if assay_type == "Cell Viability":
        y_label = "Cell Viability (%)"
    elif assay_type == "DPPH":
        y_label = "DPPH radical scavenging activity (%)"
    elif assay_type == "ELISA":
        y_label = "Concentration"
        
    ax.set_ylabel(y_label, rotation=90, fontsize=9, fontweight="bold")

    # 보조선(Baseline) 삭제 요청으로 미적용

    # ── significance 별표 ──
    y_max = max(means + sds) if len(means) > 0 else 100

    # ref_1st 기준 별표 (검정)
    ref1_display = custom_names.get(ref_1st, ref_1st) if ref_1st else "Ref1"
    sig_col_1 = f"Sig vs {ref1_display}"
    if sig_col_1 in stats_df.columns:
        for i, sig in enumerate(stats_df[sig_col_1].values):
            if sig in ("*", "**", "***"):
                bar_top = means[i] + sds[i]
                y_pos = bar_top + y_max * 0.02
                ax.text(x[i], y_pos, sig, ha="center", va="bottom",
                        fontsize=9, fontweight="bold", color="#000000")

    # ref_2nd 기준 별표 (파란)
    if ref_2nd:
        ref2_display = custom_names.get(ref_2nd, ref_2nd)
        sig_col_2 = f"Sig vs {ref2_display}"
        if sig_col_2 in stats_df.columns:
            for i, sig in enumerate(stats_df[sig_col_2].values):
                if sig in ("*", "**", "***"):
                    bar_top = means[i] + sds[i]
                    y_pos = bar_top + y_max * 0.08
                    ax.text(x[i], y_pos, sig, ha="center", va="bottom",
                            fontsize=8, fontweight="bold", color="#1565C0")

    # ── 축 정리 ──
    ax.set_ylim(0, y_max * 1.25 if y_max > 0 else 100)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=False, nbins=6))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.2, linewidth=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()

    return fig

def create_elisa_curve_chart(elisa_curve, st_concs, processed_df):
    """Standard Curve 차트 생성 (4PL / Linear 지원)."""
    from utils.analysis import logistic4

    fig, ax = plt.subplots(figsize=(5, 4))

    # ── ST 평균 데이터 수집 ──
    st_groups = {}
    for _, row in processed_df.iterrows():
        if row["Type"] == "ST" and row["Label"] in st_concs and pd.notna(row["BL_corrected"]):
            st_groups.setdefault(row["Label"], []).append(row["BL_corrected"])

    x_vals = []
    y_vals = []
    for lab, vals in st_groups.items():
        x_vals.append(st_concs[lab])
        y_vals.append(float(np.mean(vals)))

    ax.scatter(x_vals, y_vals, color="#333333", zorder=3, label="Standard Points")

    curve_type = elisa_curve.get("curve_fit", "") if elisa_curve else ""

    if elisa_curve and curve_type == "4PL" and "A" in elisa_curve:
        # ── 4PL Curve ──
        A = elisa_curve["A"]
        B = elisa_curve["B"]
        C = elisa_curve["C"]
        D = elisa_curve["D"]

        # Filter out zero/negative x for log scale
        positive_x = [v for v in x_vals if v > 0]
        if positive_x:
            x_min = min(positive_x) * 0.5
            x_max = max(positive_x) * 2.0
        else:
            x_min, x_max = 0.1, 100

        x_line = np.logspace(np.log10(x_min), np.log10(x_max), 200)
        y_line = logistic4(x_line, A, B, C, D)

        ax.plot(x_line, y_line, color="red", linestyle="--", linewidth=1.5, zorder=2, label="4PL Fit")
        ax.set_xscale("log")

        # Equation + R² annotation
        eq_text = f"{elisa_curve['equation']}\n$R^2 = {elisa_curve['r_squared']:.4f}$"
        ax.text(0.05, 0.95, eq_text, transform=ax.transAxes, fontsize=8,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8, edgecolor="#ccc"))

    elif elisa_curve and "slope" in elisa_curve:
        # ── Linear Fit ──
        slope = elisa_curve["slope"]
        intercept = elisa_curve["intercept"]
        x_min = min(x_vals) if x_vals else 0
        x_max = max(x_vals) if x_vals else 100
        x_line = np.linspace(x_min, x_max, 100)
        y_line = slope * x_line + intercept

        ax.plot(x_line, y_line, color="red", linestyle="--", linewidth=1.5, zorder=2, label="Linear Fit")

        eq_text = f"{elisa_curve['equation']}\n$R^2 = {elisa_curve['r_squared']:.4f}$"
        ax.text(0.05, 0.95, eq_text, transform=ax.transAxes, fontsize=9,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8, edgecolor="#ccc"))

    ax.set_xlabel("Concentration", fontsize=9, fontweight="bold")
    ax.set_ylabel("Absorbance (BL Corrected)", fontsize=9, fontweight="bold")
    ax.grid(alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend()
    fig.tight_layout()

    return fig
