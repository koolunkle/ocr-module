"""
[상수] 시스템 전역 상수 및 알고리즘 임계값
역할: 코드 내의 매직 넘버를 제거하고 분석 알고리즘의 주요 파라미터를 관리합니다.
"""

import re
from enum import StrEnum
from typing import Dict, Final, List, Tuple

# --- 파일 및 디렉토리 ---
ALLOWED_IMAGE_EXTS: Final = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
VIS_DIR: Final = "vis"
UNKNOWN_FILENAME: Final = "unknown"
VIS_FILENAME_FORMAT: Final = "layout_vis_p{page_num}.jpg"


class PageType(StrEnum):
    """결과 데이터의 분석 깊이를 정의하는 열거형"""
    RAW = "raw"                # 레이아웃 분석 및 일반 텍스트 정보
    STRUCTURED = "structured"  # 법원, 사건번호 등 핵심 항목 추출 성공
    ERROR = "error"            # 해당 페이지 분석 중 오류 발생


class DocKeyword(StrEnum):
    """문서에서 추출할 주요 필드의 한글 명칭 (데이터 파싱 및 스키마 매핑용)"""
    COURT = "법원"
    CASE = "사건"
    CREDITOR = "채권자"
    DEBTOR = "채무자"
    THIRD_PARTY_DEBTOR = "제3채무자"
    ORDER = "주문"
    CLAIM_AMOUNT = "청구금액"
    REASON = "이유"


# 문서 파싱 시 키워드를 찾는 순서
PARSING_ORDER: Final[List[DocKeyword]] = [
    DocKeyword.CASE,
    DocKeyword.CREDITOR,
    DocKeyword.DEBTOR,
    DocKeyword.THIRD_PARTY_DEBTOR,
    DocKeyword.ORDER,
    DocKeyword.CLAIM_AMOUNT,
    DocKeyword.REASON,
]

# 한 줄로 요약 가능한 키워드 목록
SINGLE_LINE_KEYS: Final = {DocKeyword.CASE, DocKeyword.CLAIM_AMOUNT, DocKeyword.REASON}


class FieldKey(StrEnum):
    """엔진 내부에서 사용하는 공통 데이터 필드명"""
    TEXT = "text"
    BBOX = "bbox"
    Y_CENTER = "y_center"
    Y_MIN = "y_min"
    Y_MAX = "y_max"
    X_MIN = "x_min"
    X_MAX = "x_max"


class TextTag(StrEnum):
    """텍스트 정제 시 사용하는 특수 태그"""
    SPACE = " "
    SPLIT = "[SPLIT]"


class Patterns:
    """문서 분석용 정규식 패턴 모음"""
    HEADER_MAIN = r"법[^가-힣a-zA-Z0-9]{0,10}원"  # 상단 법원명 탐색용
    HEADER_SUB = r"결[^가-힣a-zA-Z0-9]{0,10}정"   # '결정' 제목 탐색용
    CLEAN_TEXT = r"[^가-힣a-zA-Z0-9\(\)\-\[\]\<\>\!@#\$%\^&\*\s]"  # 특수문자 제거용
    LIST_ITEM = rf"(?:^|{re.escape(TextTag.SPACE)})(\d{{1,2}}[\.\)]|\d{{1,2}}(?={re.escape(TextTag.SPACE)})|\d{{1,2}}(?=[가-힣]))"
    DATE_TERMINATOR = r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}"  # 하단 날짜 패턴 (문서 끝 지점)


class Thresholds:
    """분석 알고리즘용 임계값"""
    LINE_MERGE_Y_DIFF = 15     # 행 병합 시 허용되는 Y축 높이 오차 (px)
    SECTION_GAP_LIMIT = 100    # 섹션 구분 간격 (px)
    FUZZY_MATCH_RATIO = 0.7    # 유사도 매칭 통과 기준 (0.0~1.0)

    # 문서 탐색 제약 조건
    HEADER_SEARCH_LIMIT = 10   # 상단 몇 행까지 헤더로 볼 것인지
    ORG_SEARCH_LIMIT = 5       # 법원명 탐색 행 수
    SUB_HEADER_OFFSET = 4      # 법원명 발견 후 제목 탐색 범위
    
    # 레이아웃 매칭 파라미터
    LAYOUT_MATCH_MARGIN = 10
    LAYOUT_Y_OVERLAP_RATIO = 0.2
    LAYOUT_VIS_ALPHA = 0.25    # 시각화 박스의 투명도


# 레이아웃 타입별 색상 설정 (BGR 형식)
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
