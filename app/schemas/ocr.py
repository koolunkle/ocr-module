"""
API 통신을 위한 데이터 스키마 정의
"""

from typing import List, Union, Optional
from pydantic import BaseModel, Field
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


class RawPageData(BaseModel):
    """원본 추출 데이터"""

    content: List[OCRContent] = Field(
        ..., description="추출된 텍스트 및 좌표 정보 리스트"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": [
                    {
                        "text": "음성출력용바코드",
                        "box": {"x": 2168, "y": 344, "w": 170, "h": 30},
                    }
                ]
            }
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
    type: PageType = Field(..., description="데이터 유형")
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
                            "청구금액": "금 10,000,000원",
                        },
                    },
                    {
                        "page_num": 2,
                        "type": "raw",
                        "data": {
                            "content": [
                                {
                                    "text": "음성출력용바코드",
                                    "box": {"x": 2168, "y": 344, "w": 170, "h": 30},
                                }
                            ]
                        },
                    },
                ],
            }
        }
    }
