"""
OCR 데이터 가공 및 텍스트 정제용 유틸리티
"""

import numpy as np
import re
import difflib
import cv2
from typing import List, Dict, Any
from app.core.constants import Patterns, Thresholds, FieldKey, TextTag


def preprocess_image(img_np: np.ndarray) -> np.ndarray:
    """이미지 선명도 개선 및 노이즈 제거 (적응형 이진화)"""
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np

    # 이미지 흑백 대조 강화
    binary = cv2.adaptiveThreshold(
        gray, 
        255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 
        Thresholds.IMG_ADAPTIVE_BLOCK, 
        Thresholds.IMG_ADAPTIVE_C
    )
    # 모폴로지 연산으로 노이즈 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, Thresholds.IMG_MORPH_KERNEL)
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return cv2.cvtColor(opened, cv2.COLOR_GRAY2BGR)


def merge_boxes_into_lines(
    boxes: List[List[int]],
    texts: List[str],
    y_threshold: int = Thresholds.LINE_MERGE_Y_DIFF,
) -> List[Dict[str, Any]]:
    """개별 텍스트 블록을 Y축 좌표 기준으로 행 단위로 병합"""
    if not boxes or not texts:
        return []

    data: List[Dict[str, Any]] = []
    for box, text in zip(boxes, texts):
        box_np = np.array(box)
        # 8좌표(x1,y1,...) 또는 4좌표(x_min,y_min,...) 대응
        y_coords = box_np[:, 1] if box_np.ndim == 2 else [box_np[1], box_np[3]]
        x_coords = box_np[:, 0] if box_np.ndim == 2 else [box_np[0], box_np[2]]

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
        """수집된 한 행의 아이템들을 가로(X축) 순으로 정렬하여 병합"""
        items.sort(key=lambda k: k[FieldKey.X_MIN])
        return {
            FieldKey.TEXT: " ".join([str(d[FieldKey.TEXT]) for d in items]),
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

    # 이전 아이템과 Y축 거리가 임계값 이내면 같은 행으로 간주
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
    """텍스트 내 특정 키워드 포함 여부를 유사도 기반으로 확인"""
    # 공백 및 특수문자 제거 후 비교
    clean_text = re.sub(r"[\s:.\-]", "", text)
    clean_key = keyword.replace(" ", "")
    
    if clean_key in clean_text:
        return True
    
    # 앞부분 일치 확인용
    snippet_len = len(clean_key) + 2
    target_text = clean_text[:snippet_len] if len(clean_text) > snippet_len * 2 else clean_text
    return difflib.SequenceMatcher(None, target_text, clean_key).ratio() >= threshold


def sanitize_ocr_text(text: str) -> str:
    """불필요한 기호 제거 및 중복 공백 정규화"""
    cleaned = re.sub(Patterns.CLEAN_TEXT, "", text)
    cleaned = re.sub(r"\s+", TextTag.SPACE, cleaned.strip())
    return cleaned
