# 🧬 Absorbance Analyzer — User Guide

흡광도(Absorbance) 데이터를 업로드하고 **Cell Viability / DPPH / ELISA / Fluorescence** 분석을 웹에서 바로 수행할 수 있는 Streamlit 기반 분석 도구입니다.

---

## 목차

1. [실행 방법](#1-실행-방법)
2. [지원하는 Assay 종류](#2-지원하는-assay-종류)
3. [CSV 파일 형식](#3-csv-파일-형식)
4. [Step-by-Step 사용 가이드](#4-step-by-step-사용-가이드)
   - [Step 1 — Assay 유형 선택](#step-1--assay-유형-선택)
   - [Step 2 — CSV 업로드](#step-2--csv-업로드)
   - [Step 3 — Plate Mapping](#step-3--plate-mapping)
   - [Step 4 — Sample Name 설정](#step-4--sample-name-설정)
   - [Step 5 — Reference 설정](#step-5--reference-설정)
   - [Step 6 — Quality Check](#step-6--quality-check)
   - [Step 7 — 분석 실행](#step-7--분석-실행)
   - [Step 8 — 결과 확인 및 Export](#step-8--결과-확인-및-export)
5. [ELISA / Fluorescence 전용 — Standard Curve 설정](#5-elisa--fluorescence-전용--standard-curve-설정)
6. [Layout 저장 및 불러오기](#6-layout-저장-및-불러오기)
7. [계산 공식 요약](#7-계산-공식-요약)
8. [주의사항 및 Tips](#8-주의사항-및-tips)

---

## 1. 실행 방법

```bash
# 프로젝트 폴더로 이동
cd absorbance-analysis

# 앱 실행
streamlit run app.py
```

브라우저가 자동으로 열리며 `http://localhost:8501` 에서 접속 가능합니다.

### 필요 패키지

```bash
pip install streamlit pandas numpy scipy matplotlib openpyxl python-pptx
```

---

## 2. 지원하는 Assay 종류

| Assay | 계산 방식 | Curve Fit |
|---|---|---|
| **Cell Viability** | `(Sample - Blank) / (Control - Blank) × 100 (%)` | — |
| **DPPH** | `(1 - Sample / Control) × 100 (%)` | — |
| **ELISA** | ST 기반 Standard Curve → 농도 역산 | **4PL 고정** |
| **Fluorescence** | ST 기반 Standard Curve → 농도 역산 | Linear 또는 4PL 선택 |

---

## 3. CSV 파일 형식

플레이트 리더에서 출력된 **96-well plate 형식 CSV**를 사용합니다.

- 행(Row): A~H (8행)
- 열(Column): 1~12 (12열)
- 여러 플레이트가 하나의 CSV에 포함된 경우 자동으로 분리됩니다.

> **예시:**
> ```
> Plate: Plate1
> ,1,2,3,4,5,6,7,8,9,10,11,12
> A,0.123,0.456,...
> B,0.234,0.567,...
> ...
> ```

---

## 4. Step-by-Step 사용 가이드

### Step 1 — Assay 유형 선택

페이지 상단의 라디오 버튼에서 분석 유형을 선택합니다.

```
Cell Viability  |  DPPH  |  ELISA  |  Fluorescence
```

선택한 Assay에 따라 계산 공식과 UI가 자동으로 변경됩니다.

---

### Step 2 — CSV 업로드

좌측 사이드바 **📂 1. Data Upload** 섹션에서 CSV 파일을 업로드합니다.

- 지원 형식: `.csv`, `.txt`
- 업로드 성공 시 `✅ N plates loaded` 메시지가 표시됩니다.
- 플레이트가 여러 개인 경우 **Plate Selection** 라디오 버튼으로 전환합니다.

---

### Step 3 — Plate Mapping

사이드바 **🎨 2. Mapping Tool** 에서 웰 유형을 선택하고, 메인 화면의 **Plate Grid**를 드래그하여 웰을 지정합니다.

#### 웰 유형 안내

| 유형 | 설명 |
|---|---|
| **BL (Blank)** | 블랭크 웰 — 모든 샘플에서 차감되는 배경값 |
| **NC (Neg. Ctrl)** | 음성 대조군 — 기준값(100% 또는 0%) |
| **PC (Pos. Ctrl)** | 양성 대조군 |
| **SM (Sample)** | 분석할 시료 |
| **ST (Standard)** | ELISA/Fluorescence의 Standard (농도 기준) |
| **Clear** | 지정 해제 |

#### 웰 지정 방법

1. 사이드바에서 **웰 유형** 선택
2. SM / NC / PC 의 경우 **Number** 입력 (예: SM1, SM2…)
3. 메인 화면 Plate Grid에서 해당 웰을 **클릭 또는 드래그**하여 선택

> **💡 Tip:** 같은 번호(예: SM1)를 여러 웰에 지정하면 replicate로 처리됩니다.

---

### Step 4 — Sample Name 설정

사이드바 **✏️ Sample Name Config** (접힌 상태) 를 클릭하여 펼친 후, 각 라벨에 원하는 이름을 입력합니다.

- 예: `SM1` → `Vehicle`, `PC1` → `hEGF 10ng/mL`
- 비워두면 기본 라벨(SM1, PC1 등)이 그대로 표시됩니다.

---

### Step 5 — Reference 설정

사이드바 **📐 3. Reference Config** 에서 기준 그룹을 선택합니다.

| 항목 | 설명 |
|---|---|
| **1st Reference (Control)** | 비교 기준 그룹 (보통 NC). 이 그룹 대비 t-test 수행 |
| **2nd Reference** | 추가 t-test 비교 그룹 (선택 사항) |

---

### Step 6 — Quality Check

**✅ Quality Check** 탭에서 각 웰 그룹의 CV(Coefficient of Variation)를 확인합니다.

| 색상 | CV 범위 | 의미 |
|---|---|---|
| 🟢 초록 | CV < 5% | 우수 (Good) |
| 🟡 노랑 | 5% ≤ CV < 10% | 주의 |
| 🟠 주황 | 10% ≤ CV < 20% | 경고 |
| 🔴 빨강 | CV ≥ 20% | 이상값 의심 |

- 이상값이 있는 웰은 **체크박스**를 선택하여 분석에서 제외할 수 있습니다.
- **Apply QC Changes** 버튼을 눌러 변경사항을 저장합니다.

---

### Step 7 — 분석 실행

사이드바 하단 **🚀 Run Analysis** 버튼을 클릭합니다.

- 분석이 완료되면 `✅ Analysis Complete!` 메시지가 표시됩니다.
- R² < 0.95인 경우 경고 메시지가 표시됩니다.

---

### Step 8 — 결과 확인 및 Export

**📊 Results** 탭에서 결과를 확인합니다.

#### 결과 구성

| 항목 | 내용 |
|---|---|
| **Statistics Table** | 각 그룹의 Mean, SD, N, p-value, 유의성(*/\*\*/\*\*\*) |
| **Bar Chart** | 평균 ± SD 막대그래프 (논문 스타일) |
| **Standard Curve** | ELISA/Fluorescence에서 ST 기반 피팅 곡선 + R² |
| **Processed Data** | 개별 웰 raw값, BL 보정값, 계산값 |

#### Export

- **📗 Download Excel**: Statistics, Standard Curve, Plate Map, Analysis Info 포함
- **📙 Download PPTX**: 결과 그래프 슬라이드

---

## 5. ELISA / Fluorescence 전용 — Standard Curve 설정

ELISA 또는 Fluorescence를 선택하면 사이드바에 **ST Configuration** 섹션이 나타납니다.

### ST 농도 설정

| 항목 | 설명 | 예시 |
|---|---|---|
| **Number of STs** | Standard 개수 | 8 |
| **Start Conc (ST1)** | 최고 농도 | 3200 |
| **End Conc** | 최저 농도 (보통 0) | 0 |
| **Fold Dilution** | 희석 배수 | 2 (2배 희석) |

→ **Generate STs** 버튼 클릭 시 ST1~ST8 농도 자동 생성

### Curve Fit 방법

| Assay | 방법 | 특징 |
|---|---|---|
| **ELISA** | **4PL 고정** | `y = (A-D)/(1+(x/C)^B) + D` |
| **Fluorescence** | Linear 또는 4PL 선택 | Linear: `y = mx + b` |

#### 4PL 파라미터 의미

| 파라미터 | 의미 |
|---|---|
| **A** | Minimum asymptote (시료 없을 때 최소값) |
| **B** | Hill slope (곡선 기울기) |
| **C** | Inflection point / EC50 (변곡점) |
| **D** | Maximum asymptote (포화 최대값) |

> **농도 역산 공식:** `x = C × ((A-D)/(y-D) - 1)^(1/B)`

### ST 매핑 방법

1. **Generate STs** 버튼으로 ST1~STn 생성
2. **Select ST to Map** 드롭다운에서 ST 번호 선택 (예: ST1)
3. Plate Grid에서 해당 웰 드래그 지정
4. ST2, ST3… 반복

---

## 6. Layout 저장 및 불러오기

동일한 플레이트 레이아웃을 반복 사용하는 경우 JSON으로 저장해두면 편리합니다.

### 저장

사이드바 **💾 Load / Save Layout** → **📥 Export Mapping as JSON** 클릭

저장되는 정보:
- Well mapping (BL/NC/PC/SM/ST 위치)
- Custom sample names
- Excluded wells
- ST 농도 설정

### 불러오기

1. **📤 Upload Mapping JSON** 에 저장된 JSON 파일 업로드
2. **Apply Uploaded Layout** 버튼 클릭
3. 레이아웃 자동 적용 후 **Run Analysis** 진행

---

## 7. 계산 공식 요약

### Cell Viability
```
Cell Viability (%) = (Sample_BL_corrected / Control_BL_corrected) × 100
```

### DPPH Radical Scavenging Activity
```
Scavenging Activity (%) = (1 - Sample / Control) × 100
```

### ELISA / Fluorescence (4PL)
```
Standard Curve:  y = (A - D) / (1 + (x/C)^B) + D
농도 역산:       x = C × ((A - D) / (y - D) - 1)^(1/B)
```

### ELISA / Fluorescence (Linear)
```
Standard Curve:  y = mx + b
농도 역산:       x = (y - b) / m
```

### BL Correction (전 Assay 공통)
```
BL_corrected = Raw_value - Blank_mean
```

### 통계
```
Mean, SD (ddof=1), t-test: Welch's t-test (equal_var=False)
유의성: * p < 0.05,  ** p < 0.01,  *** p < 0.001,  ns: not significant
```

---

## 8. 주의사항 및 Tips

- **BL(Blank)은 반드시 지정**하세요. BL 없이는 BL 보정이 0으로 처리됩니다.
- **ELISA에서 ST는 Generate STs 후 매핑**해야 농도 정보가 연결됩니다.
- **R² < 0.95** 경고가 표시되면 이상값 웰을 QC 탭에서 제거한 뒤 재분석하세요.
- **4PL fitting이 실패**하는 경우 (ST 개수 부족, 농도 범위 좁음 등) 에러 메시지가 표시됩니다. ST 데이터를 확인하세요.
- Excel 파일의 **Standard Curve 차트**는 4PL 곡선 데이터가 시트에 직접 기록되므로 편집 가능합니다.
- 여러 플레이트를 분석할 때는 각 플레이트별로 **Run Analysis**를 실행해야 합니다.
