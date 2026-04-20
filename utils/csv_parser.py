"""
96-well plate CSV/TXT 파서 (유연한 버전).

주요 특징:
- pd.to_numeric(errors='coerce')로 숫자만 추출, 비숫자는 NaN 처리
- 96개 미만 데이터도 허용 (부분 측정 지원)
- 다양한 구분자 자동 감지 (comma, tab, whitespace)
- 파일 내 텍스트(날짜, Tm값, 기기 설정 등) 자동 무시
- 데이터 영역(숫자 밀집 영역)만 자동 슬라이싱

파싱 전략:
  1단계: 전체 파일을 pd.read_csv로 읽어 pd.to_numeric 적용
  2단계: "숫자 밀도"가 높은 연속 행 블록을 찾음
  3단계: 각 블록에서 유효 숫자가 있는 열 범위만 자동 슬라이싱
  4단계: 8×12 DataFrame으로 패딩하여 반환
"""
import pandas as pd
import numpy as np
import io
import re


# ── 데이터 행 인식 기준 ──
# 한 행에서 "연속적으로 의미 있는 숫자"가 몇 개 이상이어야 plate 데이터인지
MIN_NUMS_PER_ROW = 3
# 한 블록에 최소 몇 행 있어야 유효 plate로 인정하는지
MIN_ROWS_PER_BLOCK = 2


def parse_plate_csv(uploaded_file) -> dict:
    """
    업로드된 CSV/TXT에서 96-well 데이터를 유연하게 추출.

    Returns
    -------
    {"PLATE 1": DataFrame(8×12), ...}
    빈 셀은 NaN으로 유지됨. 데이터가 없으면 빈 dict 반환(에러 없음).
    """
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    text = _decode_raw(raw)

    # pd.to_numeric 기반 유연한 자동 감지 (메인 전략)
    blocks = _find_plates_flexible(text)

    # 방법 1 실패 시 구조화된 파서 시도 (기존 plate reader 호환)
    if not blocks:
        lines = text.strip().splitlines()
        blocks = _find_plates_structured(lines)

    if not blocks:
        return {}

    return {f"PLATE {i+1}": df for i, df in enumerate(blocks)}


def get_parse_summary(plates: dict) -> dict:
    """파싱 결과 요약 정보를 반환 (Streamlit UI 표시용)."""
    if not plates:
        return {
            "valid": False,
            "message": "⚠️ 유효한 수치 데이터를 찾을 수 없습니다.",
            "plates": []
        }

    summaries = []
    for name, df in plates.items():
        total = df.size
        valid = int(df.notna().sum().sum())
        summaries.append({
            "name": name,
            "shape": f"{df.shape[0]}×{df.shape[1]}",
            "valid_cells": valid,
            "nan_cells": total - valid,
            "total_cells": total,
        })

    return {
        "valid": True,
        "message": f"✅ {len(plates)}개 plate 로드 완료",
        "plates": summaries
    }


# ═══════════════════════════════════════════════════════════
#  인코딩 처리
# ═══════════════════════════════════════════════════════════

def _decode_raw(raw):
    """바이트를 문자열로 디코딩 (여러 인코딩 시도)."""
    if isinstance(raw, str):
        return raw.lstrip("\ufeff")
    for enc in ("utf-8", "utf-8-sig", "cp949", "latin1"):
        try:
            return raw.decode(enc).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").lstrip("\ufeff")


# ═══════════════════════════════════════════════════════════
#  메인 전략: pd.to_numeric 기반 유연한 자동 감지
# ═══════════════════════════════════════════════════════════

def _find_plates_flexible(text):
    """
    pd.to_numeric(errors='coerce') 기반 유연한 데이터 영역 감지.

    알고리즘:
    1. 파일을 DataFrame으로 읽기 (여러 구분자 시도)
    2. 모든 셀에 pd.to_numeric(errors='coerce') 적용
    3. 각 행의 "연속 숫자 셀" 비율로 데이터 행 판별
       - 메타(Plate=1, temp=21.1 등)는 숫자가 흩어져있고
       - 실제 데이터는 숫자가 이웃 셀에 연속으로 나타남
    4. 연속 데이터 행 블록 → 유효 열 범위 슬라이싱 → plate 생성
    """
    df = None

    # 여러 구분자로 파싱 시도
    for sep, kwargs in [
        (',', {}),
        ('\t', {}),
        (r'\s+', {"engine": "python"}),
    ]:
        try:
            trial = pd.read_csv(
                io.StringIO(text), sep=sep, header=None,
                on_bad_lines='skip', dtype=str, **kwargs
            )
            if trial.shape[1] >= 2:
                df = trial
                break
        except Exception:
            continue

    if df is None:
        return []

    # 모든 셀을 숫자로 변환 (pd.to_numeric, errors='coerce')
    numeric_df = df.apply(lambda col: pd.to_numeric(col, errors='coerce'))

    # ── 각 행의 "연속 숫자 밀도" 계산 ──
    # 메타데이터 행 vs 실제 plate 데이터 행을 구분하는 핵심 로직
    # 실제 plate 데이터: ,0.885,1.161,1.367,0.857,... → 연속된 숫자 블록
    # 메타 행: 1,1,텍스트,21.1,21.2,텍스트 → 숫자가 흩어져 있음
    data_mask = _calc_data_row_mask(numeric_df, df)

    if not data_mask.any():
        return []

    # 연속된 데이터 행 블록 찾기
    blocks = []
    current_rows = []

    for idx in range(len(data_mask)):
        if data_mask.iloc[idx]:
            current_rows.append(idx)
        else:
            if len(current_rows) >= MIN_ROWS_PER_BLOCK:
                _extract_block(numeric_df, current_rows, blocks)
            current_rows = []

    if len(current_rows) >= MIN_ROWS_PER_BLOCK:
        _extract_block(numeric_df, current_rows, blocks)

    return blocks


def _calc_data_row_mask(numeric_df, str_df):
    """
    각 행이 plate 데이터인지 판별하는 마스크 생성.

    판별 기준:
    1. 행의 유효 숫자 수 >= MIN_NUMS_PER_ROW
    2. "최대 연속 숫자 길이"가 MIN_NUMS_PER_ROW 이상
       (메타: 1,1,NaN,21.1,21.2,NaN → 최대 연속=2, plate: NaN,0.885,1.161,... → 최대 연속=7)
    """
    mask = pd.Series(False, index=numeric_df.index)

    for idx in numeric_df.index:
        # 1. 특정 키워드(Temperature 등)가 포함된 메타데이터 행 완전 무시
        str_row_vals = str_df.loc[idx].fillna("").astype(str).str.lower()
        if any(keyword in " ".join(str_row_vals) for keyword in ["temperature", "time", "wavelength", "kinetic"]):
            continue

        row = numeric_df.loc[idx]
        valid_count = row.notna().sum()

        if valid_count < MIN_NUMS_PER_ROW:
            continue

        # 최대 연속 non-NaN 길이 계산
        max_consec = _max_consecutive_valid(row)

        if max_consec >= MIN_NUMS_PER_ROW:
            mask[idx] = True

    return mask


def _max_consecutive_valid(series):
    """Series에서 연속 non-NaN 값의 최대 길이를 반환."""
    max_count = 0
    current = 0
    for val in series:
        if pd.notna(val):
            current += 1
            max_count = max(max_count, current)
        else:
            current = 0
    return max_count


def _extract_block(numeric_df, row_indices, blocks):
    """연속 행 인덱스에서 데이터 블록 추출 후 blocks 리스트에 추가."""
    block_df = numeric_df.iloc[row_indices].copy()

    # ── 유효 열 범위 자동 슬라이싱 ──
    # 각 열에서 non-NaN이 하나라도 있는 열만 선택
    valid_cols = block_df.notna().any(axis=0)
    valid_col_indices = [i for i, v in enumerate(valid_cols) if v]

    if not valid_col_indices:
        return

    # 연속된 열 범위 찾기 (가장 큰 연속 범위 사용)
    col_start, col_end = _find_largest_consecutive_range(valid_col_indices)
    block_df = block_df.iloc[:, col_start:col_end + 1]

    if block_df.shape[1] < 1:
        return

    # 최대 12열까지 (오른쪽 기준, 즉 마지막 12열 우선)
    if block_df.shape[1] > 12:
        block_df = block_df.iloc[:, -12:]

    # 8행 단위로 plate 분할
    for start in range(0, len(row_indices), 8):
        chunk = block_df.iloc[start:start + 8]
        blocks.append(_to_df_flexible(chunk.values.tolist()))


def _find_largest_consecutive_range(indices):
    """정수 인덱스 리스트에서 가장 긴 연속 범위의 (start, end)를 반환."""
    if not indices:
        return (0, 0)

    best_start = indices[0]
    best_end = indices[0]
    cur_start = indices[0]
    cur_end = indices[0]

    for i in range(1, len(indices)):
        if indices[i] == cur_end + 1:
            cur_end = indices[i]
        else:
            if (cur_end - cur_start) > (best_end - best_start):
                best_start, best_end = cur_start, cur_end
            cur_start = indices[i]
            cur_end = indices[i]

    if (cur_end - cur_start) > (best_end - best_start):
        best_start, best_end = cur_start, cur_end

    return (best_start, best_end)


# ═══════════════════════════════════════════════════════════
#  폴백: 구조화된 plate reader CSV 파싱 (기존 로직)
# ═══════════════════════════════════════════════════════════

def _extract_nums_coerce(parts):
    """pd.to_numeric(errors='coerce')로 숫자 추출. 변환 불가 → NaN."""
    results = []
    for p in parts:
        p = p.strip().strip('"')
        if not p:
            results.append(np.nan)
            continue
        results.append(pd.to_numeric(p, errors='coerce'))
    return results


def _count_valid(nums):
    """리스트에서 NaN이 아닌 값의 개수."""
    return sum(1 for v in nums if pd.notna(v))


def _pad_to_12(nums):
    """리스트를 정확히 12개로 맞춤 (부족하면 NaN 패딩, 초과면 자르기)."""
    return (list(nums) + [np.nan] * 12)[:12]


def _classify_line(line):
    """
    행 분류 (유연한 버전).
    Returns: ("data", [12 values]) | ("blank", None) | ("skip", None)
    """
    stripped = line.strip()

    # 빈 행
    if not stripped or all(c in ",\t " for c in stripped):
        return ("blank", None)

    parts = re.split(r"[,\t]", stripped)
    first = parts[0].strip().strip('"')

    # Temperature 헤더 → 스킵
    if first.lower().startswith("temperature"):
        return ("skip", None)

    # A~H 문자로 시작 → plate reader row label
    if len(first) == 1 and first.upper() in "ABCDEFGH":
        nums = _extract_nums_coerce(parts[1:])
        if _count_valid(nums) >= MIN_NUMS_PER_ROW:
            return ("data", _pad_to_12(nums))
        return ("skip", None)

    # 첫 셀이 숫자 (온도 등)
    first_val = pd.to_numeric(first, errors='coerce')
    if pd.notna(first_val):
        nums_after = _extract_nums_coerce(parts[1:])
        if _count_valid(nums_after) >= MIN_NUMS_PER_ROW:
            if len(nums_after) >= 12:
                return ("data", nums_after[:12])
            return ("data", _pad_to_12(nums_after))

        nums_all = _extract_nums_coerce(parts)
        if _count_valid(nums_all) >= MIN_NUMS_PER_ROW:
            if len(nums_all) >= 12:
                return ("data", nums_all[:12])
            return ("data", _pad_to_12(nums_all))

        return ("skip", None)

    # 첫 셀 비어있음 (B~H행)
    if first == "":
        nums = _extract_nums_coerce(parts[1:])
        if _count_valid(nums) >= MIN_NUMS_PER_ROW:
            return ("data", _pad_to_12(nums))
        return ("skip", None)

    # 그 외 텍스트 → 스킵
    return ("skip", None)


def _find_plates_structured(lines):
    """
    구조화된 plate reader CSV에서 plate 블록 찾기.
    - blank 행 또는 헤더가 나오면 블록을 끊음
    - 8행 미만 블록도 허용 (NaN으로 패딩)
    """
    blocks = []
    current_block = []

    for line in lines:
        kind, nums = _classify_line(line)

        if kind == "data":
            current_block.append(nums)
            if len(current_block) == 8:
                blocks.append(_to_df_flexible(current_block))
                current_block = []
        elif kind == "blank":
            if len(current_block) >= MIN_ROWS_PER_BLOCK:
                blocks.append(_to_df_flexible(current_block))
            current_block = []
        elif kind == "skip":
            if len(current_block) >= MIN_ROWS_PER_BLOCK:
                blocks.append(_to_df_flexible(current_block))
            current_block = []

    if len(current_block) >= MIN_ROWS_PER_BLOCK:
        blocks.append(_to_df_flexible(current_block))

    return blocks


# ═══════════════════════════════════════════════════════════
#  공통 유틸리티
# ═══════════════════════════════════════════════════════════

def _to_df_flexible(data):
    """
    가변 크기 데이터를 8×12 DataFrame으로 변환.
    부족한 행/열은 NaN으로 패딩.
    """
    rows_idx = list("ABCDEFGH")
    cols_idx = [str(i) for i in range(1, 13)]

    # 최대 8행
    data = list(data)[:8]

    # 각 행을 12열로 맞춤
    padded = []
    for row in data:
        r = list(row) if hasattr(row, '__iter__') else [row]
        r = (r + [np.nan] * 12)[:12]
        # float 변환 (안전하게)
        r = [float(v) if pd.notna(v) else np.nan for v in r]
        padded.append(r)

    # 8행 미만이면 NaN 행 추가
    while len(padded) < 8:
        padded.append([np.nan] * 12)

    return pd.DataFrame(padded, index=rows_idx, columns=cols_idx)
