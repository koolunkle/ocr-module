"""
[데이터] API 통신용 스키마 정의
역할: Pydantic을 사용하여 요청 및 응답 데이터의 구조와 유효성을 정의합니다.
"""

from typing import List, Optional, Union

from pydantic import BaseModel, Field, RootModel

from app.constants import PageType


class OCRBox(BaseModel):
    """텍스트 영역의 좌표 정보 (x, y, 가로, 세로)"""

    x: int = Field(..., description="X축 시작점")
    y: int = Field(..., description="Y축 시작점")
    w: int = Field(..., description="영역 너비")
    h: int = Field(..., description="영역 높이")


class OCRContent(BaseModel):
    """텍스트 내용과 해당 좌표의 결합체"""

    text: str = Field(..., description="인식된 텍스트 내용")
    box: OCRBox = Field(..., description="텍스트의 좌표 정보")


class LayoutRegion(BaseModel):
    """문서 내의 개별 레이아웃 영역 (텍스트, 제목, 표 등)"""

    type: str = Field(..., description="영역의 성격 (예: text, table, title)")
    score: float = Field(..., description="영역 분류에 대한 신뢰도 점수")
    rect: OCRBox = Field(..., description="영역 전체의 좌표")
    lines: List[str] = Field(default_factory=list, description="영역 내부에 포함된 텍스트 행 목록")


class RawPageData(RootModel):
    """비구조화된 페이지 데이터 (레이아웃 영역 목록 또는 개별 텍스트 박스 목록)"""

    root: Union[List[LayoutRegion], List[OCRContent]] = Field(
        ..., description="추출된 텍스트 및 레이아웃 상세 정보"
    )


class StructuredPageData(BaseModel):
    """문서에서 추출된 비즈니스 핵심 데이터 (사건 정보 및 당사자 등)"""

    court_name: Optional[str] = Field(None, alias="법원", description="발행 기관")
    case_number: Optional[str] = Field(None, alias="사건", description="참조 사건 번호")
    creditor: Optional[Union[str, List[str]]] = Field(None, alias="채권자", description="채권자 정보")
    debtor: Optional[Union[str, List[str]]] = Field(None, alias="채무자", description="채무자 정보")
    third_party_debtor: Optional[Union[str, List[str]]] = Field(None, alias="제3채무자", description="제3채무자 정보")
    order: Optional[Union[str, List[str]]] = Field(None, alias="주문", description="결정문 본문(주문) 내용")
    claim_amount: Optional[str] = Field(None, alias="청구금액", description="청구된 금액")
    reason: Optional[str] = Field(None, alias="이유", description="결정 사유")

    model_config = {
        "populate_by_name": True,  # 영문 필드명과 한국어 Alias 모두 사용 가능
        "extra": "ignore",         # 정의되지 않은 추가 필드는 무시
    }


class ErrorPageData(BaseModel):
    """페이지별 분석 실패 시 에러 메시지 정보"""

    message: str = Field(..., description="오류 발생 원인 및 상세 내용")


class PageResult(BaseModel):
    """페이지별 최종 분석 결과"""

    page_num: int = Field(..., description="문서 내 페이지 번호")
    type: PageType = Field(..., description="데이터 분석 수준 (raw, structured, error)")
    data: Union[StructuredPageData, RawPageData, ErrorPageData] = Field(..., description="분석된 상세 데이터")


class OCRResponse(BaseModel):
    """API 최종 응답 규격"""

    filename: str = Field(..., description="업로드된 원본 파일명")
    pages: List[PageResult] = Field(..., description="각 페이지별 분석 결과 리스트")
