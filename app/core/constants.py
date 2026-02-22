"""
시스템 공통 상수 및 텍스트 추출 패턴 정의
"""

import re
from enum import StrEnum

# 허용 파일 확장자
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class PageType(StrEnum):
    """처리 결과 타입"""

    RAW = "raw"
    STRUCTURED = "structured"
    ERROR = "error"


class Keyword(StrEnum):
    """문서 분석용 핵심 키워드"""

    ORG = "법원"
    ID = "사건"
    ATTR_A = "채권자"
    ATTR_B = "채무자"
    ATTR_C = "제3채무자"
    CONTENT_MAIN = "주문"
    VALUE = "청구금액"
    DESC = "이유"


# 파싱 우선 순위 목록
STRUCTURED_PARSING_KEYS = [
    Keyword.ID,
    Keyword.ATTR_A,
    Keyword.ATTR_B,
    Keyword.ATTR_C,
    Keyword.CONTENT_MAIN,
    Keyword.VALUE,
    Keyword.DESC,
]

# 단일 텍스트 블록으로 병합할 키워드
SIMPLE_TEXT_KEYS = {Keyword.ID, Keyword.VALUE, Keyword.DESC}


class FieldKey(StrEnum):
    """데이터 스키마 키"""

    TEXT = "text"
    BBOX = "bbox"
    Y_CENTER = "y_center"
    Y_MIN = "y_min"
    Y_MAX = "y_max"
    X_MIN = "x_min"
    X_MAX = "x_max"


class Tags(StrEnum):
    """텍스트 가공용 태그"""

    SPACE = "[SP]"
    SPLIT = "[SPLIT]"


class Patterns:
    """텍스트 탐색용 정규식 패턴"""

    HEADER_MAIN = r"법[^가-힣a-zA-Z0-9]{0,10}원"
    HEADER_SUB = r"결[^가-힣a-zA-Z0-9]{0,10}정"

    # 특수문자 정제
    CLEAN_TEXT_DISALLOWED = r"[^가-힣a-zA-Z0-9\(\)\-\[\]\<\>\!@#\$%\^&\*\s]"

    # 목록 번호 분리 (예: 1., 2))
    LIST_ITEM_SPLIT = rf"(?:^|{re.escape(Tags.SPACE)})(\d{{1,2}}[\.\)]|\d{{1,2}}(?={re.escape(Tags.SPACE)})|\d{{1,2}}(?=[가-힣]))"

    # 하단 정보 감지 (날짜 등)
    TERMINATOR_DATE = r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}"


class Thresholds:
    """알고리즘 임계값"""

    LINE_MERGE_Y_DIFF = 15  # 행 병합 Y축 오차
    SECTION_GAP_LIMIT = 100  # 섹션 종료 간격
    KEYWORD_MATCH_RATIO = 0.7  # 유사도 매칭 기준
