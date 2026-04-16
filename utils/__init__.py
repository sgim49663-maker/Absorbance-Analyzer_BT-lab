# utils package
import re


def natural_sort_key(s):
    """SM1, SM2, ..., SM10, SM11 순서로 정렬하기 위한 키 함수."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r'(\d+)', s)
    ]
