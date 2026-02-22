"""
OCR 처리 엔드포인트 정의
"""

import json
import logging
from typing import Tuple, Optional, List

from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from app.schemas.ocr import OCRResponse
from app.services.ocr_service import ocr_service
from app.api.v1.dependencies import validate_image_file

logger = logging.getLogger(__name__)
router = APIRouter()


def parse_target_pages(pages_str: Optional[str]) -> Optional[List[int]]:
    """페이지 번호 파싱 (예: '1,2,3' -> [1, 2, 3])"""
    if not pages_str:
        return None
    try:
        pages = [int(p.strip()) for p in pages_str.split(",") if p.strip()]
        return pages if pages else None
    except ValueError:
        raise HTTPException(
            status_code=400, detail="페이지 형식이 잘못되었습니다. (예: 1,3,5)"
        )


@router.post("/", response_model=OCRResponse)
async def process_ocr(
    image_data: Tuple[Image.Image, str] = Depends(validate_image_file),
    pages: Optional[str] = Form(
        None, description="처리할 페이지 (예: 1,3,5 / 공백 시 전체)", examples=["1,3,5"]
    ),
):
    """문서 이미지 분석 (일괄 응답)"""
    image, filename = image_data
    target_pages = parse_target_pages(pages)

    try:
        return ocr_service.process_image(image, filename, target_pages)
    except Exception as e:
        logger.error(f"처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 처리 오류")


@router.post(
    "/stream",
    responses={
        200: {
            "description": "문서 이미지 분석 (SSE 스트리밍 응답). 각 'data:' 필드에 PageResult 객체가 JSON 형태로 포함됩니다.",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"page_num": 1, "type": "raw", "data": {...}}\n\n'
                }
            },
        }
    },
)
async def process_ocr_stream(
    image_data: Tuple[Image.Image, str] = Depends(validate_image_file),
    pages: Optional[str] = Form(
        None, description="처리할 페이지 (예: 1,3,5 / 공백 시 전체)", examples=["1,3,5"]
    ),
):
    """문서 이미지 분석 (SSE 스트리밍 응답)"""
    image, filename = image_data
    target_pages = parse_target_pages(pages)

    try:

        def iter_file():
            for result in ocr_service.process_image_generator(
                image, filename, target_pages
            ):
                yield f"data: {json.dumps(result.model_dump(by_alias=True), ensure_ascii=False)}\n\n"

        return StreamingResponse(iter_file(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"스트리밍 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 스트리밍 오류")
