# Changelog

All notable changes to the Absorbance Analysis Web project will be documented in this file.

---

## [2026-04-16] 4PL (4-Parameter Logistic) Curve Fitting 추가

### Added
- **4PL Curve Fitting 엔진** (`utils/analysis.py`):
  - `logistic4(x, A, B, C, D)` 함수 정의 — 4-Parameter Logistic 정방향 수식 `y = (A-D) / (1 + (x/C)^B) + D`
  - `solve_4pl(y, A, B, C, D)` 함수 정의 — Inverse 4PL로 OD값 → 농도 역산 `x = C × ((A-D)/(y-D) - 1)^(1/B)`
  - `scipy.optimize.curve_fit`으로 A, B, C, D 최적 파라미터 자동 산출
  - R² = 1 - SS_res / SS_tot 방식으로 적합도 직접 계산

- **Assay별 Curve Fit 분리**:
  - **ELISA**: 4PL 고정 적용 (selectbox 없이 자동), 사이드바에 info 메시지 표시
  - **Fluorescence**: Linear / 4PL 선택 가능한 selectbox 제공
  - **Exponential** 옵션 완전 제거

- **Standard Curve 차트 (웹, `utils/visualization.py`)**:
  - 4PL 선택 시 `logspace`로 200점 곡선 생성 후 렌더링
  - X축 자동 로그 스케일 (`ax.set_xscale("log")`) 적용 — 저농도 구간 가시성 확보
  - 차트 상단에 equation + R² 텍스트 박스 표시

- **Excel Export (`utils/export_excel.py`)**:
  - Analysis Info 시트에 Curve Fit 종류, Equation, R², 4PL 파라미터(A/B/C/D) 기록
  - Standard Curve 차트: 4PL 곡선 데이터(50점)를 시트에 직접 기록 후 Line Series로 추가 (openpyxl 기본 trendline 미지원 → 동일 곡선 수동 구현)
  - X축 로그 스케일 (`scatter.x_axis.scaling.logBase = 10`) 적용
  - 차트 제목에 equation + R² 표시하여 웹 그래프와 완전 일치

### Changed
- ELISA description box 문구를 4PL 수식 기반 설명으로 업데이트

---

## [2026-04-14] Quality Check CV, Layout Save/Load, ST Curve Fix

### Added
- **QC Quality Check CV 표시**: SD 대신 CV(Coefficient of Variation) 값을 표시하도록 변경. CV = SD / Mean × 100%. 색상 기준: 🟢 5% 미만 (Good), 🟡 5% 이상 (Yellow), 🟠 10% 이상 (Orange), 🔴 20% 이상 (Red).
- **Sample Name Config 토글**: 사이드바의 Sample Name Config 섹션을 `st.expander`로 감싸 접고 펼 수 있도록 변경. 기본값은 접힌 상태.
- **Plate Mapping 저장/불러오기**: 사이드바에 `💾 Load / Save Layout` 섹션 추가. 현재 플레이트의 well mapping, custom sample names, excluded wells, ST 농도 설정을 JSON 파일로 내보내고, 새 데이터에 동일한 레이아웃을 업로드하여 즉시 적용 가능.

### Changed
- **Exponential 수식 표기 개선**: 웹 차트의 Exponential 수식 표기를 `ln(y) = mx + c` 형식에서 `y = c·e^(bx)` 형식으로 변경하여 엑셀 추세선 표기와 시각적으로 통일.

### Fixed
- **ST Curve Exponential 필터링 순서 수정**: Exponential fitting 시 개별 replicate 값이 0 이하인 경우를 먼저 제외하던 로직을 수정. 이제 replicate 평균을 먼저 계산한 뒤 평균이 0 이하인 ST 그룹만 제외하도록 변경하여 엑셀 추세선과 동일한 결과를 보장.

### Removed
- 화면 우측 하단 스크롤 이동 버튼 (▲/▼) 제거.

---

## [Unreleased] - 2026-04-14 (Earlier)

### Added
- **Exponential Curve Fitting**: Implemented an exponential regression logic ($y = A \cdot e^{Bx} \rightarrow \ln(y) = mx + c$) for Standard Curves. Available as a "Curve Fit Method" UI dropdown. Non-positive absorbance values are mathematically and gracefully excluded.
- **Fluorescence ST Integration**: Fluorescence assay tab now supports ST (Standard) capabilities mapping exactly like the ELISA assay.
- **Dynamic Excel Charts**: Transformed Matplotlib static exported images into deep-customized native & editable `openpyxl` Scatter and Bar charts.

### Changed
- **Graph Aesthetics**: Completely modernized Matplotlib Web UI charts and exported Excel `openpyxl` charts. All bars are now uniformly filled with pure white (`#FFFFFF`) with prominent black borders (`#000000`).
- **Error Bar Plotting**: Altered error handling logic inside `utils/visualization.py` and `utils/export_excel.py` to plot symmetric Standard Deviation (SD) upper and lower limits simultaneously (`errBarType="both"`).
- **Plate Map Clarity**: Redrawn the "Processed Data" mapping in Excel to represent unmapped or skipped wells strictly as clean grey `#D9D9D9` without any residual UI text placeholders.

### Removed
- Removed the arbitrary auxiliary `sysDash` baseline line generated at `y=100` from both the web plots and Excel spreadsheets to streamline the visual style.

### Fixed
- Fixed an openpyxl `TypeError: GraphicalProperties.__init__() got an unexpected keyword argument 'line'` by replacing `gp.line` with `gp.ln` within the graph rendering module (`export_excel.py`).
- Resolved a syntax parsing error triggered by dropping native `if` statements during a code file injection block within `app.py`.

### Advanced ST Curve Handling
- ELISA & Fluorescence standard curve regressions now dynamically average the replicate measurements inside a specific ST group (e.g. ST1 mean) prior to generating models, matching exact expected scientific behaviors rather than plotting independent replicate dots.

### Excel Export Accuracy
- Reconciled tracking discrepancy between Streamlit Web UI curves and Native Excel curves by standardizing ST extraction to purely group-averaged figures on both ecosystems.
- Fixed natively transparent axes formatting in 'openpyxl' BarCharts by explicitly applying boundary weight solid lines across X and Y axes boundaries.

### Final Layout Polish
- Reduced Excel chart Plot Area left-margin one last time to aggressively maximize horizontal scaling without dropping the Y-axis label.
