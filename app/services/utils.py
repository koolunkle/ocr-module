"""
이미지 처리 및 텍스트 데이터 가공 유틸리티
"""

import numpy as np
import re
import difflib
import cv2
from typing import List, Dict, Any
from app.core.constants import Patterns, Thresholds, FieldKey, Tags


def preprocess_image(img_np: np.ndarray) -> np.ndarray:
    """이미지 선명도 개선 및 노이즈 제거 (적응형 이진화)"""
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 15
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)


def merge_boxes_into_lines(
    boxes: List[List[int]],
    texts: List[str],
    y_threshold: int = Thresholds.LINE_MERGE_Y_DIFF,
) -> List[Dict[str, Any]]:
    """OCR 개별 단어들을 위치(Y축) 기준으로 행 단위 병합"""
    if not boxes or not texts:
        return []

    data: List[Dict[str, Any]] = []
    for box, text in zip(boxes, texts):
        box_np = np.array(box)
        y_coords = box_np[:, 1] if box_np.ndim == 2 else [box_np[1], box_np[3]]
        x_coords = box_np[:, 0] if box_np.ndim == 2 else [box_np[0], box_np[2]]

        data.append(
            {
                FieldKey.TEXT.value: text,
                FieldKey.Y_CENTER.value: float(np.mean(y_coords)),
                FieldKey.Y_MIN.value: float(np.min(y_coords)),
                FieldKey.Y_MAX.value: float(np.max(y_coords)),
                FieldKey.X_MIN.value: float(np.min(x_coords)),
                FieldKey.X_MAX.value: float(np.max(x_coords)),
            }
        )

    data.sort(key=lambda k: k[FieldKey.Y_CENTER.value])
    lines: List[Dict[str, Any]] = []
    if not data:
        return lines

    current_line_items = [data[0]]

    def _create_line(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        items.sort(key=lambda k: k[FieldKey.X_MIN.value])
        return {
            FieldKey.TEXT.value: " ".join([str(d[FieldKey.TEXT.value]) for d in items]),
            FieldKey.Y_MIN.value: min(d[FieldKey.Y_MIN.value] for d in items),
            FieldKey.Y_MAX.value: max(d[FieldKey.Y_MAX.value] for d in items),
            FieldKey.Y_CENTER.value: sum(d[FieldKey.Y_CENTER.value] for d in items)
            / len(items),
            FieldKey.BBOX.value: [
                int(min(d[FieldKey.X_MIN.value] for d in items)),
                int(min(d[FieldKey.Y_MIN.value] for d in items)),
                int(max(d[FieldKey.X_MAX.value] for d in items)),
                int(max(d[FieldKey.Y_MAX.value] for d in items)),
            ],
        }

    for i in range(1, len(data)):
        item = data[i]
        last_item = current_line_items[-1]
        if (
            abs(item[FieldKey.Y_CENTER.value] - last_item[FieldKey.Y_CENTER.value])
            < y_threshold
        ):
            current_line_items.append(item)
        else:
            lines.append(_create_line(current_line_items))
            current_line_items = [item]

    if current_line_items:
        lines.append(_create_line(current_line_items))
    return lines


def is_fuzzy_match(
    text: str, keyword: str, threshold: float = Thresholds.KEYWORD_MATCH_RATIO
) -> bool:
    """유사도 기반 키워드 매칭 여부 확인"""
    clean_text = re.sub(r"[\s:.\-]", "", text)
    clean_key = keyword.replace(" ", "")
    if clean_key in clean_text:
        return True
    snippet_len = len(clean_key) + 2
    target_text = (
        clean_text[:snippet_len] if len(clean_text) > snippet_len * 2 else clean_text
    )
    return difflib.SequenceMatcher(None, target_text, clean_key).ratio() >= threshold


def sanitize_ocr_text(text: str) -> str:
    """불필요한 특수문자 제거 및 공백 정규화"""
    cleaned = re.sub(Patterns.CLEAN_TEXT_DISALLOWED, "", text)
    cleaned = re.sub(r"\s+", Tags.SPACE.value, cleaned.strip())
    return cleaned
