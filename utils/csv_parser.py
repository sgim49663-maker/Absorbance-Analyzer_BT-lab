"""
96-well plate CSV 파서.

Plate reader CSV 실제 구조 (엑셀 셀 기준 B2~M9):
    Temperature(°C),1,2,3,...,12       ← row 1: 헤더 → 스킵
    27.6,0.049,0.0494,...              ← row 2: A행 (첫 셀=온도, 뒤 12개=데이터)
    ,0.049,0.1815,...                  ← row 3: B행 (첫 셀 비어있음)
    ...
    ,0.049,0.0497,...                  ← row 9: H행
    ,,,,,,,,,,,,                       ← 빈 행 (plate 구분)
    Temperature(°C),1,2,3,...,12       ← 다음 plate 헤더
    27.7,0.0491,...                    ← 다음 plate A행
    ...

핵심 규칙:
  1. "Temperature" 로 시작하는 행 → 스킵 (헤더)
  2. 온도값으로 시작하는 행 → 뒤 12개 숫자가 A행 데이터
  3. 첫 셀 비어있고 뒤에 숫자 12개 → B~H행 데이터
  4. 첫 셀이 A~H 문자 → 데이터 행 (다른 plate reader 호환)
  5. 연속 8행 → 하나의 96-well plate
"""
import pandas as pd
import numpy as np
import io
import re


def parse_plate_csv(uploaded_file) -> dict:
    """
    업로드된 CSV에서 96-well (8행 × 12열) 데이터를 모두 찾아 반환.

    Returns
    -------
    {"PLATE 1": DataFrame(8×12), "PLATE 2": DataFrame(8×12), ...}
    """
    raw = uploaded_file.read()
    if isinstance(raw, bytes):
        for enc in ("utf-8", "utf-8-sig", "cp949", "latin1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
    else:
        text = raw

    # BOM 제거
    text = text.lstrip("\ufeff")

    lines = text.strip().splitlines()
    blocks = _find_plates(lines)

    if not blocks:
        raise ValueError(
            "96-well plate 형식의 8×12 숫자 블록을 찾을 수 없습니다.\n"
            "CSV 형식을 확인해 주세요."
        )

    return {f"PLATE {i+1}": b for i, b in enumerate(blocks)}


# ── 내부 함수 ──────────────────────────────────────────────


def _extract_nums(parts):
    """문자열 리스트에서 float 변환 가능한 값만 추출."""
    nums = []
    for p in parts:
        p = p.strip().strip('"')
        if not p:
            continue
        try:
            nums.append(float(p))
        except ValueError:
            continue
    return nums


def _classify_line(line):
    """
    행을 분류.
    Returns: ("data", [12 floats]) | ("blank", None) | ("skip", None)
    """
    stripped = line.strip()

    # 빈 행 (비어있거나 쉼표/탭만 있는 경우) → plate 구분자
    if not stripped or all(c in ",\t " for c in stripped):
        return ("blank", None)

    parts = re.split(r"[,\t]", stripped)
    first = parts[0].strip().strip('"')

    # ── Temperature 헤더 행 → 스킵 ──
    if first.lower().startswith("temperature"):
        return ("skip", None)

    # ── 첫 셀이 A~H 문자 → 데이터 행 (다른 plate reader 호환) ──
    if len(first) == 1 and first.upper() in "ABCDEFGH":
        nums = _extract_nums(parts[1:])
        if len(nums) >= 12:
            return ("data", nums[:12])
        return ("skip", None)

    # ── 첫 셀이 숫자 ──
    try:
        float(first)
        # 먼저 13열 형식 확인 (첫 셀=온도, 뒤 12개=데이터)
        nums_after = _extract_nums(parts[1:])
        if len(nums_after) >= 12:
            return ("data", nums_after[:12])
        # 12열 형식 확인 (모든 셀이 데이터)
        nums_all = _extract_nums(parts)
        if len(nums_all) >= 12:
            return ("data", nums_all[:12])
        return ("skip", None)
    except ValueError:
        pass

    # ── 첫 셀이 비어있음 → 데이터 행 (B~H) ──
    if first == "":
        nums = _extract_nums(parts[1:])
        if len(nums) >= 12:
            return ("data", nums[:12])
        return ("skip", None)

    # 그 외 → 스킵
    return ("skip", None)


def _find_plates(lines):
    """
    모든 데이터 행을 모아서 8행 단위로 plate를 구성.
    blank 행 또는 Temperature 헤더가 나오면 블록을 끊음.
    """
    blocks = []
    current_block = []

    for line in lines:
        kind, nums = _classify_line(line)

        if kind == "data":
            current_block.append(nums)
        elif kind == "blank":
            # 빈 행 → 블록 끊기
            if len(current_block) >= 8:
                blocks.append(_to_df(current_block[:8]))
            current_block = []
        elif kind == "skip":
            # Temperature 헤더 등 → 이전 블록 저장 후 리셋
            if len(current_block) >= 8:
                blocks.append(_to_df(current_block[:8]))
            current_block = []

    # 마지막 블록
    if len(current_block) >= 8:
        blocks.append(_to_df(current_block[:8]))

    return blocks


def _to_df(data):
    """8×12 리스트 → DataFrame."""
    return pd.DataFrame(
        data,
        index=list("ABCDEFGH"),
        columns=[str(i) for i in range(1, 13)],
    )
