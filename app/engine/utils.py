"""
[엔진] OCR 데이터 가공 및 텍스트 정제용 유틸리티
역할: 이미지 전처리(현재 미사용), 텍스트 블록 병합(Line Merge), 유사도 매칭 등 공통 알고리즘 제공
"""

import difflib
import re
from typing import Any, Dict, Final, List, Sequence

import numpy as np

from app.constants import FieldKey, Patterns, TextTag, Thresholds

# --- 지역 상수 (Local Constants) ---
FUZZY_MARGIN: Final = 2  # 유사도 매칭 시 키워드 앞뒤 탐색 여유분

# 불필요한 기호 제거용 정규식
_PTRN_GARBAGE: Final = re.compile(Patterns.CLEAN_TEXT)

# 연속된 공백 통합용 정규식
_PTRN_WHITESPACE: Final = re.compile(r"\s+")

# 유사도 비교를 위한 텍스트 정규화용 정규식
_PTRN_FUZZY_NORM: Final = re.compile(r"[\s:.\-]")


def merge_boxes_into_lines(
    boxes: Sequence[Sequence[int]],
    texts: Sequence[str],
    y_threshold: int = Thresholds.LINE_MERGE_Y_DIFF,
) -> List[Dict[str, Any]]:
    """흩어진 텍스트 블록들을 Y축 좌표 기준으로 동일한 행(Line)으로 병합"""
    if not boxes or not texts:
        return []

    # 1. 원본 데이터를 다루기 쉬운 정규화된 딕셔너리 형태로 변환
    items = []
    for box, text in zip(boxes, texts):
        box_np = np.array(box)
        x_coords = box_np[0::2]
        y_coords = box_np[1::2]

        items.append({
            FieldKey.TEXT: text,
            FieldKey.Y_CENTER: float(np.mean(y_coords)),
            FieldKey.Y_MIN: float(np.min(y_coords)),
            FieldKey.Y_MAX: float(np.max(y_coords)),
            FieldKey.X_MIN: float(np.min(x_coords)),
            FieldKey.X_MAX: float(np.max(x_coords)),
        })

    # Y축 중심점 기준으로 오름차순 정렬
    items.sort(key=lambda x: x[FieldKey.Y_CENTER])

    lines: List[Dict[str, Any]] = []
    if not items:
        return lines

    def _flush_line(current_items: List[Dict[str, Any]]):
        """수집된 행 내부 아이템들을 X축 순서로 정렬하여 하나의 문자열로 결합"""
        current_items.sort(key=lambda x: x[FieldKey.X_MIN])
        lines.append({
            FieldKey.TEXT: " ".join(str(d[FieldKey.TEXT]) for d in current_items),
            FieldKey.Y_MIN: min(d[FieldKey.Y_MIN] for d in current_items),
            FieldKey.Y_MAX: max(d[FieldKey.Y_MAX] for d in current_items),
            FieldKey.Y_CENTER: sum(d[FieldKey.Y_CENTER] for d in current_items) / len(current_items),
            FieldKey.BBOX: [
                int(min(d[FieldKey.X_MIN] for d in current_items)),
                int(min(d[FieldKey.Y_MIN] for d in current_items)),
                int(max(d[FieldKey.X_MAX] for d in current_items)),
                int(max(d[FieldKey.Y_MAX] for d in current_items)),
            ],
        })

    current_line_items = [items[0]]

    # 행 병합 루프: 인접한 텍스트 블록 간의 Y축 차이가 임계값 이내면 같은 행으로 처리
    for i in range(1, len(items)):
        item = items[i]
        last_item = current_line_items[-1]

        if abs(item[FieldKey.Y_CENTER] - last_item[FieldKey.Y_CENTER]) < y_threshold:
            current_line_items.append(item)
        else:
            _flush_line(current_line_items)
            current_line_items = [item]

    if current_line_items:
        _flush_line(current_line_items)

    return lines


def is_fuzzy_match(
    text: str, keyword: str, threshold: float = Thresholds.FUZZY_MATCH_RATIO
) -> bool:
    """오타가 섞인 OCR 텍스트에서도 키워드를 찾아낼 수 있도록 유사도 기반 매칭 수행"""
    # 텍스트 정규화 (공백 및 특수문자 제거)
    clean_text = _PTRN_FUZZY_NORM.sub("", text)
    clean_key = keyword.replace(" ", "")

    # 1. 완전 포함 관계 확인
    if clean_key in clean_text:
        return True

    # 2. 유사도 비율 계산 (difflib 활용)
    snippet_len = len(clean_key) + FUZZY_MARGIN
    target_text = clean_text[:snippet_len] if len(clean_text) > snippet_len * 2 else clean_text
    return difflib.SequenceMatcher(None, target_text, clean_key).ratio() >= threshold


def sanitize_ocr_text(text: str) -> str:
    """OCR 결과에서 유효하지 않은 특수기호를 제거하고 공백을 정돈"""
    cleaned = _PTRN_GARBAGE.sub("", text)
    return _PTRN_WHITESPACE.sub(TextTag.SPACE, cleaned).strip()
