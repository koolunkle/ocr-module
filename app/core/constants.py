"""
시스템 전역 상수 및 알고리즘 파라미터
"""

import re
from enum import StrEnum
from typing import Final, Dict, Tuple

# --- 시스템 및 경로 ---
ALLOWED_IMAGE_EXTS: Final = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
VIS_DIR: Final = "vis"


class PageType(StrEnum):
    """결과 데이터 유형"""
    RAW = "raw"                # 일반 텍스트 및 레이아웃
    STRUCTURED = "structured"  # 비즈니스 구조화 완료
    ERROR = "error"            # 처리 실패


# --- 문서 분석 도메인 ---
class DocKeyword(StrEnum):
    """분석 식별자"""
    ORG = "법원"
    ID = "사건"
    ATTR_A = "채권자"
    ATTR_B = "채무자"
    ATTR_C = "제3채무자"
    CONTENT_MAIN = "주문"
    VALUE = "청구금액"
    DESC = "이유"


PARSING_ORDER: Final = [
    DocKeyword.ID,
    DocKeyword.ATTR_A,
    DocKeyword.ATTR_B,
    DocKeyword.ATTR_C,
    DocKeyword.CONTENT_MAIN,
    DocKeyword.VALUE,
    DocKeyword.DESC,
]

SINGLE_LINE_KEYS: Final = {DocKeyword.ID, DocKeyword.VALUE, DocKeyword.DESC}


# --- 데이터 처리 키 ---
class FieldKey(StrEnum):
    """내부 데이터 필드명"""
    TEXT = "text"
    BBOX = "bbox"
    Y_CENTER = "y_center"
    Y_MIN = "y_min"
    Y_MAX = "y_max"
    X_MIN = "x_min"
    X_MAX = "x_max"


class TextTag(StrEnum):
    """텍스트 가공 태그"""
    SPACE = " "
    SPLIT = "[SPLIT]"


class Patterns:
    """정규식 패턴"""
    HEADER_MAIN = r"법[^가-힣a-zA-Z0-9]{0,10}원"
    HEADER_SUB = r"결[^가-힣a-zA-Z0-9]{0,10}정"
    CLEAN_TEXT = r"[^가-힣a-zA-Z0-9\(\)\-\[\]\<\>\!@#\$%\^&\*\s]"
    LIST_ITEM = rf"(?:^|{re.escape(TextTag.SPACE)})(\d{{1,2}}[\.\)]|\d{{1,2}}(?={re.escape(TextTag.SPACE)})|\d{{1,2}}(?=[가-힣]))"
    DATE_TERMINATOR = r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}"


# --- 알고리즘 및 시각화 파라미터 ---
class Thresholds:
    """분석 임계값"""
    LINE_MERGE_Y_DIFF = 15     # 행 병합 오차 (px)
    SECTION_GAP_LIMIT = 100    # 섹션 구분 간격 (px)
    FUZZY_MATCH_RATIO = 0.7    # 유사도 매칭 기준

    # 이미지 처리
    IMG_ADAPTIVE_BLOCK = 25
    IMG_ADAPTIVE_C = 15
    IMG_MORPH_KERNEL = (2, 1)

    # 문서 탐색 범위
    HEADER_SEARCH_LIMIT = 10
    ORG_SEARCH_LIMIT = 5
    SUB_HEADER_OFFSET = 4
    
    # 레이아웃 매칭
    LAYOUT_MATCH_MARGIN = 10
    LAYOUT_Y_OVERLAP_RATIO = 0.2
    LAYOUT_VIS_ALPHA = 0.25    # 시각화 투명도


# 레이아웃 타입별 고대비 색상 (BGR)
LAYOUT_COLORS: Final[Dict[str, Tuple[int, int, int]]] = {
    "text": (180, 50, 0),      # 파랑
    "title": (0, 100, 0),      # 초록
    "figure": (120, 0, 120),   # 보라
    "table": (0, 0, 180),      # 빨강
    "header": (0, 100, 200),   # 주황
    "footer": (100, 100, 0),   # 하늘
    "reference": (60, 60, 60), # 회색
    "equation": (150, 80, 0),  # 남색
}
DEFAULT_LAYOUT_COLOR: Final[Tuple[int, int, int]] = (100, 100, 100)
