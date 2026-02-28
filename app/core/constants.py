"""
프로젝트 전역에서 사용하는 상수와 패턴 정의
"""

import re
from enum import StrEnum

# --- 시스템 설정 ---
# 허용하는 이미지 확장자
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class PageType(StrEnum):
    """OCR 처리 결과 상태"""
    RAW = "raw"                # 기본 텍스트 추출
    STRUCTURED = "structured"  # 구조화 분석 완료
    ERROR = "error"            # 처리 실패


# --- 문서 분석 키워드 ---
class DocKeyword(StrEnum):
    """문서 구조 분석을 위한 식별자"""
    ORG = "법원"
    ID = "사건"
    ATTR_A = "채권자"
    ATTR_B = "채무자"
    ATTR_C = "제3채무자"
    CONTENT_MAIN = "주문"
    VALUE = "청구금액"
    DESC = "이유"


# 파싱 시 키워드를 찾는 순서
PARSING_ORDER = [
    DocKeyword.ID,
    DocKeyword.ATTR_A,
    DocKeyword.ATTR_B,
    DocKeyword.ATTR_C,
    DocKeyword.CONTENT_MAIN,
    DocKeyword.VALUE,
    DocKeyword.DESC,
]

# 단일 문장으로 취급할 항목 (줄바꿈 없이 병합)
SINGLE_LINE_KEYS = {DocKeyword.ID, DocKeyword.VALUE, DocKeyword.DESC}


# --- 데이터 처리 및 가공 ---
class FieldKey(StrEnum):
    """내부 데이터 처리에 쓰이는 필드명"""
    TEXT = "text"
    BBOX = "bbox"
    Y_CENTER = "y_center"
    Y_MIN = "y_min"
    Y_MAX = "y_max"
    X_MIN = "x_min"
    X_MAX = "x_max"


class TextTag(StrEnum):
    """텍스트 정제 및 구분용 특수 태그"""
    SPACE = " "        # 기본 공백
    SPLIT = "[SPLIT]"  # 데이터 분리용 임시 태그


class Patterns:
    """텍스트 탐색 및 정제용 정규식"""
    # 문서 헤더(결정문 여부) 감지
    HEADER_MAIN = r"법[^가-힣a-zA-Z0-9]{0,10}원"
    HEADER_SUB = r"결[^가-힣a-zA-Z0-9]{0,10}정"

    # 유효하지 않은 특수문자 제거 패턴
    CLEAN_TEXT = r"[^가-힣a-zA-Z0-9\(\)\-\[\]\<\>\!@#\$%\^&\*\s]"

    # 목록 번호 패턴 (예: 1., 2) 등)
    LIST_ITEM = rf"(?:^|{re.escape(TextTag.SPACE)})(\d{{1,2}}[\.\)]|\d{{1,2}}(?={re.escape(TextTag.SPACE)})|\d{{1,2}}(?=[가-힣]))"

    # 문서 끝단 정보(날짜 등) 감지
    DATE_TERMINATOR = r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}"


# --- 알고리즘 파라미터 ---
class Thresholds:
    """텍스트 병합 및 매칭 임계값"""
    LINE_MERGE_Y_DIFF = 15     # 같은 행으로 판단할 Y축 오차 (px)
    SECTION_GAP_LIMIT = 100    # 다음 섹션으로 넘어가기 전 최대 간격 (px)
    FUZZY_MATCH_RATIO = 0.7    # 키워드 유사도 매칭 기준 (0~1)

    # 이미지 전처리 (이진화 및 노이즈 제거)
    IMG_ADAPTIVE_BLOCK = 25    # 적응형 이진화 블록 크기
    IMG_ADAPTIVE_C = 15        # 적응형 이진화 차감 상수
    IMG_MORPH_KERNEL = (2, 1)  # 모폴로지 연산 커널 크기

    # 문서 분석 탐색 범위
    HEADER_SEARCH_LIMIT = 10   # 문서 상단에서 헤더를 찾을 최대 행 수
    ORG_SEARCH_LIMIT = 5       # 법원명 탐색 범위
    SUB_HEADER_OFFSET = 4      # 법원명 발견 후 결정문 제목을 찾을 범위
