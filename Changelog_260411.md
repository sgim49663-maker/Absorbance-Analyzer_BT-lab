# Changelog 260411

## 🚀 새로운 기능 (New Features)
1. **다중 분석 지원 (Multi-Assay Support)**
   - `Cell Viability (CCK-8 assay)`
   - `DPPH Radical Scavenging Assay`
   - `ELISA`
   - `Fluorescence`
   - 메인 화면에 접속 시 위 분석 방식 중 하나를 선택하여 진행할 수 있도록 구현했습니다. 

2. **사전 데이터 품질 검사 (Quality Check; QC)**
   - 데이터 분석 이전에 각 샘플들의 변동성(SD)을 확인할 수 있는 **Quality Check** 탭을 신설했습니다.
   - SD 0.5 이상의 값을 갖는 샘플은 빨간색 에러 메시지로 하이라이트됩니다.
   - 사용자가 개별 well을 선택적으로 제외할 수 있으며 제외된 값들은 분석 및 그래프에서 완전히 배제됩니다.

3. **ELISA 전용 Standard 곡선 시스템**
   - ST 농도를 자동 생성(시작 농도, 끝 농도, 희석 배수 설정)하는 기능을 추가했습니다.
   - 분석 시 ST 포인트를 기반으로 선형 회귀 곡선(Linear Regression)을 산출하고 $R^2$가 0.95 이하일 경우 경고 메시지가 표시됩니다.

## 🛠 수정 및 개선 사항 (Improvements & Bug Fixes)
1. **UI 영문화 및 직관성 향상**
   - 사용자가 요청한 가이드라인에 따라 앱 내 주요 텍스트들이 간단명료한 영문으로 수정되었습니다. (e.g. Absorbance Analyzer, Export, Data Upload)
   - 각 분석 탭(Assay Type)별 매핑 Tool과 템플릿(PC 등 기본 설정값)이 유동적으로 변화합니다.

2. **계산 로직 수정**
   - DPPH 분석에서는 사용자의 확인대로 Blank(BL) 개념을 포함하지 않도록 수정하여 모두 0으로 처리하거나 제외하고 `(1 - {sample/NC_mean}) * 100` 수식이 작동하게 변경했습니다.
   - ELISA의 흡광도를 농도로 역산출 시 음수로 나오는 값은 생물학적 타당성에 따라 `최소값 0`으로 유지하도록 조정했습니다.

3. **그래프 및 차트(Visualization)**
   - 매트플롯립(Matplotlib) 바 차트 및 엑셀(Excel) 내부 차트 모두 오차막대(Error bar)가 양수(+) 방향만 그려지도록 변경했습니다.
   - `utils/visualization.py`의 x축 라벨 텍스트(샘플 명)가 기울어지지 않고 0도로 똑바로 서도록 변경했습니다.
   - 분석 종류마다 결과 차트의 y축 제목이 다르게 변하도록("Cell Viability (%)", "Concentration", "DPPH radical scavenging activity (%)") 적용했습니다.
   - 메인 웹 화면(UI) 상단 분석 계산 로직 설명의 폰트 크기를 줄이고, 분수 대신 1줄짜리 수식으로 변경해 모니터 등에서의 가독성을 높였습니다.

4. **내보내기 (Export: Excel & PPTX)**
   - **Excel**: `Statistics` 시트의 `P-Value` 숫자 서식을 `0.00E+00` 지수 표기법으로 수정했습니다. 기존 Chart 시트를 제거하고 Statistics 시트 내 자체 엑셀 그래프(수정 및 편집 가능한 BarChart)를 생성하도록 설계했습니다.
   - 엑셀 자체 차트를 그릴 때 참조하는 데이터 셀(`Sample`, `Mean`, `SD`)을 숨김 처리 해제함으로써 엑셀 버전과 상관없이 차트가 안전하게 표현되도록 오류를 방지했습니다.
   - `None` 값 또는 사용자가 지정한 Negative Control(`NC`) 그룹의 평균값을 찾아 차트 전체에 걸쳐 빨간색 가로 점선의 기준선(Baseline)을 그리도록 고도화되었습니다.
   - `Processed Data` 맵핑 시트에서 사용자가 지정하지 않은 웰 자리의 기존 `Unmapped` 텍스트 출력을 생략하고 빈칸 모양에 연한 회색 배경만 적용시켰습니다.
   - **PPTX**: 불필요한 거대 표가 출력되던 3번째 슬라이드(Data Table) 생성 로직을 제거하고, 제목과 메인 이미지 그래프 딱 두 장의 슬라이드만 깔끔하게 내보내지도록 간소화했습니다.
