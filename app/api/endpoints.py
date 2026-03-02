"""
[API] OCR 처리 엔드포인트 정의
역할: 클라이언트로부터 이미지를 받아 분석을 수행하고 결과를 반환하는 API 인터페이스
"""

import json
import logging
from typing import Final, List, Optional, Tuple

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from app.api.dependencies import validate_image_file
from app.schemas import OCRResponse
from app.engine.processor import ocr_service

logger = logging.getLogger(__name__)
router = APIRouter()

# --- 지역 상수 (Local Constants) ---
SSE_PREFIX: Final = "data: "
SSE_SUFFIX: Final = "\n\n"
STREAM_CONTENT_TYPE: Final = "text/event-stream"
DEFAULT_PAGE_EXAMPLE: Final = ["1,3,5"]


def parse_target_pages(pages_str: Optional[str]) -> Optional[List[int]]:
    """문자열 형태의 페이지 번호 목록(예: '1,3,5')을 정수 리스트로 변환"""
    if not pages_str:
        return None
    try:
        pages = [int(p.strip()) for p in pages_str.split(",") if p.strip()]
        # 1페이지 이상의 유효한 번호만 필터링
        valid_pages = [p for p in pages if p > 0]
        return valid_pages if valid_pages else None
    except ValueError:
        raise HTTPException(
            status_code=400, detail="페이지 번호 형식이 잘못되었습니다. (예: 1,3,5)"
        )


@router.post("/", response_model=OCRResponse)
async def process_ocr(
    image_data: Tuple[Image.Image, str] = Depends(validate_image_file),
    pages: Optional[str] = Form(
        None,
        description="분석할 페이지 번호 (예: 1,3 / 비워두면 전체 페이지 처리)",
        examples=DEFAULT_PAGE_EXAMPLE,
    ),
):
    """
    [일괄 처리] 업로드된 이미지를 분석하여 모든 결과를 한 번에 응답
    """
    image, filename = image_data
    target_pages = parse_target_pages(pages)

    try:
        # async 엔드포인트에 맞춰 비동기 메서드를 await 호출 (이벤트 루프 블로킹 방지)
        return await ocr_service.process_image_async(image, filename, target_pages)
    except Exception as e:
        logger.exception(f"OCR 처리 중 오류 발생 (파일명: {filename})")
        raise HTTPException(status_code=500, detail="서버에서 이미지를 처리하는 중 오류가 발생했습니다.")


@router.post(
    "/stream",
    responses={
        200: {
            "description": "SSE(Server-Sent Events) 스트리밍 응답. 각 페이지 분석이 완료되는 즉시 데이터를 전송합니다.",
            "content": {
                STREAM_CONTENT_TYPE: {
                    "example": f'{SSE_PREFIX}{{"page_num": 1, "type": "raw", "data": {{...}}}}{SSE_SUFFIX}'
                }
            },
        }
    },
)
async def process_ocr_stream(
    image_data: Tuple[Image.Image, str] = Depends(validate_image_file),
    pages: Optional[str] = Form(
        None,
        description="분석할 페이지 번호 (예: 1,3 / 비워두면 전체 페이지 처리)",
        examples=DEFAULT_PAGE_EXAMPLE,
    ),
):
    """
    [스트리밍 처리] 대용량 문서(TIF 등) 분석 시 페이지별 결과가 나오는 대로 즉시 전송 (SSE 방식)
    """
    image, filename = image_data
    target_pages = parse_target_pages(pages)

    def iter_results():
        """분석 결과를 SSE 포맷으로 실시간 생성하는 제너레이터"""
        try:
            for result in ocr_service.process_image_generator(image, filename, target_pages):
                # JSON 데이터를 SSE 규격('data: ...\n\n')에 맞춰 직렬화
                yield f"{SSE_PREFIX}{json.dumps(result.model_dump(by_alias=True), ensure_ascii=False)}{SSE_SUFFIX}"
        except Exception as e:
            logger.exception(f"스트리밍 분석 중 오류 발생 (파일명: {filename})")
            error_data = {"error": "Processing interrupted", "detail": str(e)}
            yield f"{SSE_PREFIX}{json.dumps(error_data, ensure_ascii=False)}{SSE_SUFFIX}"

    return StreamingResponse(iter_results(), media_type=STREAM_CONTENT_TYPE)
