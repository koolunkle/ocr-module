"""
OCR 데이터 가공 및 텍스트 정제용 유틸리티
"""

import numpy as np
import re
import difflib
import cv2
from typing import List, Dict, Any, Final, Sequence
from app.core.constants import Patterns, Thresholds, FieldKey, TextTag

# 유효하지 않은 특수문자 및 기호 제거용
_PTRN_GARBAGE: Final = re.compile(Patterns.CLEAN_TEXT)

# 연속된 공백을 단일 공백으로 통합용
_PTRN_WHITESPACE: Final = re.compile(r"\s+")

# 유사도 비교를 위한 텍스트 정규화용 (공백 및 기호 제거)
_PTRN_FUZZY_NORM: Final = re.compile(r"[\s:.\-]")


def preprocess_image(img_np: np.ndarray) -> np.ndarray:
    """이미지 선명도 개선 및 노이즈 제거 (적응형 이진화)"""
    gray = (
        cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        if img_np.ndim == 3 and img_np.shape[2] == 3
        else img_np
    )

    # 이미지 흑백 대조 강화
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        Thresholds.IMG_ADAPTIVE_BLOCK,
        Thresholds.IMG_ADAPTIVE_C,
    )
    # 모폴로지 연산으로 노이즈 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, Thresholds.IMG_MORPH_KERNEL)
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)


def merge_boxes_into_lines(
    boxes: Sequence[Sequence[int]],
    texts: Sequence[str],
    y_threshold: int = Thresholds.LINE_MERGE_Y_DIFF,
) -> List[Dict[str, Any]]:
    """개별 텍스트 블록을 위치(Y축) 기준으로 행 단위 병합"""
    if not boxes or not texts:
        return []

    # 1. 원본 데이터를 처리하기 쉬운 딕셔너리 리스트로 변환
    data = []
    for box, text in zip(boxes, texts):
        box_np = np.array(box)
        # RapidOCR의 8점 좌표 [x1,y1,x2,y2,x3,y3,x4,y4] 대응
        x_coords = box_np[0::2]
        y_coords = box_np[1::2]

        data.append(
            {
                FieldKey.TEXT: text,
                FieldKey.Y_CENTER: float(np.mean(y_coords)),
                FieldKey.Y_MIN: float(np.min(y_coords)),
                FieldKey.Y_MAX: float(np.max(y_coords)),
                FieldKey.X_MIN: float(np.min(x_coords)),
                FieldKey.X_MAX: float(np.max(x_coords)),
            }
        )

    # Y축 중심값 기준 정렬
    data.sort(key=lambda k: k[FieldKey.Y_CENTER])

    lines: List[Dict[str, Any]] = []
    if not data:
        return lines

    current_line_items = [data[0]]

    def _create_line(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """수집된 항목들을 가로순으로 정렬하여 하나의 라인 데이터 생성"""
        items.sort(key=lambda k: k[FieldKey.X_MIN])
        return {
            FieldKey.TEXT: " ".join(str(d[FieldKey.TEXT]) for d in items),
            FieldKey.Y_MIN: min(d[FieldKey.Y_MIN] for d in items),
            FieldKey.Y_MAX: max(d[FieldKey.Y_MAX] for d in items),
            FieldKey.Y_CENTER: sum(d[FieldKey.Y_CENTER] for d in items) / len(items),
            FieldKey.BBOX: [
                int(min(d[FieldKey.X_MIN] for d in items)),
                int(min(d[FieldKey.Y_MIN] for d in items)),
                int(max(d[FieldKey.X_MAX] for d in items)),
                int(max(d[FieldKey.Y_MAX] for d in items)),
            ],
        }

    # 행 병합 수행
    for i in range(1, len(data)):
        item = data[i]
        last_item = current_line_items[-1]

        if abs(item[FieldKey.Y_CENTER] - last_item[FieldKey.Y_CENTER]) < y_threshold:
            current_line_items.append(item)
        else:
            lines.append(_create_line(current_line_items))
            current_line_items = [item]

    if current_line_items:
        lines.append(_create_line(current_line_items))

    return lines


def is_fuzzy_match(
    text: str, keyword: str, threshold: float = Thresholds.FUZZY_MATCH_RATIO
) -> bool:
    """유사도 기반 키워드 매칭"""
    # 텍스트 정규화
    clean_text = _PTRN_FUZZY_NORM.sub("", text)
    clean_key = keyword.replace(" ", "")

    if clean_key in clean_text:
        return True

    snippet_len = len(clean_key) + 2
    target_text = (
        clean_text[:snippet_len] if len(clean_text) > snippet_len * 2 else clean_text
    )
    return difflib.SequenceMatcher(None, target_text, clean_key).ratio() >= threshold


def sanitize_ocr_text(text: str) -> str:
    """텍스트 정제"""
    cleaned = _PTRN_GARBAGE.sub("", text)
    return _PTRN_WHITESPACE.sub(TextTag.SPACE, cleaned).strip()
