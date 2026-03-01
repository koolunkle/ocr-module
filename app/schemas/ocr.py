"""
API 통신을 위한 데이터 스키마 정의
"""

from typing import List, Union, Optional
from pydantic import BaseModel, Field, RootModel
from app.core.constants import PageType


class OCRBox(BaseModel):
    """단일 텍스트 상자 정보 (x, y, w, h)"""

    x: int = Field(..., examples=[2168])
    y: int = Field(..., examples=[344])
    w: int = Field(..., examples=[170])
    h: int = Field(..., examples=[30])


class OCRContent(BaseModel):
    """텍스트와 좌표 정보가 결합된 아이템"""

    text: str = Field(..., description="추출된 텍스트", examples=["음성출력용바코드"])
    box: OCRBox = Field(..., description="텍스트 좌표 (x, y, w, h)")


class LayoutRegion(BaseModel):
    """문서 내 개별 영역 정보 (텍스트, 제목, 표 등)"""

    type: str = Field(..., description="영역 타입 (text, title, table 등)", examples=["text"])
    score: float = Field(..., description="분류 신뢰도", examples=[0.9791])
    rect: OCRBox = Field(..., description="영역 전체 좌표 (x, y, w, h)")
    lines: List[str] = Field(default_factory=list, description="해당 영역에 포함된 텍스트 라인들")


class RawPageData(RootModel):
    """원본 추출 데이터 (리스트 직접 반환)
    레이아웃 분석 성공 시 List[LayoutRegion], 실패 시 List[OCRContent]를 반환
    """

    root: Union[List[LayoutRegion], List[OCRContent]] = Field(
        ..., description="추출된 텍스트 및 레이아웃 영역 정보 목록"
    )

    model_config = {
        "json_schema_extra": {
            "example": [
                {
                    "type": "text",
                    "score": 0.9791,
                    "rect": {"x": 404, "y": 2222, "w": 1835, "h": 383},
                    "lines": ["텍스트 라인 1", "텍스트 라인 2"]
                }
            ]
        }
    }


class StructuredPageData(BaseModel):
    """구조화된 추출 데이터"""

    org_name: Optional[str] = Field(
        None, alias="법원", description="발행 기관", examples=["서울중앙지방법원"]
    )
    ref_id: Optional[str] = Field(
        None, alias="사건", description="참조 식별자", examples=["2023타채12345"]
    )
    attr_a: Optional[Union[str, List[str]]] = Field(
        None, alias="채권자", examples=["홍길동"]
    )
    attr_b: Optional[Union[str, List[str]]] = Field(
        None, alias="채무자", examples=["김철수"]
    )
    attr_c: Optional[Union[str, List[str]]] = Field(
        None, alias="제3채무자", examples=["주식회사 한국은행"]
    )
    content_body: Optional[Union[str, List[str]]] = Field(
        None,
        alias="주문",
        examples=["채무자의 제3채무자에 대한 별지 기재 채권을 압류한다."],
    )
    value_data: Optional[str] = Field(
        None, alias="청구금액", examples=["금 10,000,000원"]
    )
    description: Optional[str] = Field(
        None,
        alias="이유",
        examples=["이 사건 신청은 이유 있으므로 주문과 같이 결정한다."],
    )

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "법원": "서울중앙지방법원",
                "사건": "2023타채12345",
                "채권자": "홍길동",
                "채무자": "김철수",
                "제3채무자": "주식회사 한국은행",
                "주문": "채무자의 제3채무자에 대한 별지 기재 채권을 압류한다.",
                "청구금액": "금 10,000,000원",
                "이유": "이 사건 신청은 이유 있으므로 주문과 같이 결정한다.",
            }
        },
    }


class ErrorPageData(BaseModel):
    """에러 정보"""

    message: str = Field(..., description="에러 내용")


class PageResult(BaseModel):
    """페이지별 처리 결과"""

    page_num: int = Field(..., description="페이지 번호")
    type: PageType = Field(..., description="데이터 유형 (raw, structured, error)")
    data: Union[StructuredPageData, RawPageData, ErrorPageData] = Field(
        ..., description="상세 데이터"
    )


class OCRResponse(BaseModel):
    """최종 응답 규격"""

    filename: str = Field(..., description="파일명", examples=["document.tif"])
    pages: List[PageResult] = Field(..., description="페이지 결과 목록")

    model_config = {
        "json_schema_extra": {
            "example": {
                "filename": "document.tif",
                "pages": [
                    {
                        "page_num": 1,
                        "type": "structured",
                        "data": {
                            "법원": "서울중앙지방법원",
                            "사건": "2023타채12345",
                            "채권자": "홍길동",
                            "채무자": "김철수",
                        },
                    },
                    {
                        "page_num": 2,
                        "type": "raw",
                        "data": [
                            {
                                "type": "text",
                                "score": 0.9791,
                                "rect": {"x": 404, "y": 2222, "w": 1835, "h": 383},
                                "lines": ["텍스트 라인 1"]
                            }
                        ],
                    },
                ],
            }
        }
    }
