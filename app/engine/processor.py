"""
[엔진] OCR 및 문서 분석 통합 프로세서
역할: Layout 분석과 OCR을 병렬로 실행하고 최종 결과를 조합하는 컨트롤러
"""

import asyncio
import concurrent.futures
import logging
from typing import Any, Dict, Final, Generator, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageSequence
from rapidocr import RapidOCR

from app.config import settings
from app.constants import PageType
from app.schemas import (
    ErrorPageData,
    OCRBox,
    OCRContent,
    PageResult,
    RawPageData,
)
from app.engine.layout import layout_service
from app.engine.parser import parser_service

logger = logging.getLogger(__name__)

# --- 지역 상수 (Local Constants) ---
# 한 페이지 내에서 실행되는 AI 엔진 수 (Layout + OCR)
PAGE_INFERENCE_WORKERS: Final = 2
THREAD_NAME_PREFIX: Final = "OCRWorker"
INNER_THREAD_PREFIX: Final = "InferenceWorker"


class OCRProcessor:
    """RapidOCR/Layout 엔진을 활용한 문서 처리 파이프라인"""

    def __init__(self):
        self._engine: Optional[RapidOCR] = None
        # 다중 페이지 병렬 처리를 위한 메인 스레드 풀
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.OCR_MAX_WORKERS, thread_name_prefix=THREAD_NAME_PREFIX
        )
        # 페이지 내부 병렬 추론을 위한 전용 스레드 풀 (매번 생성하지 않고 재사용)
        self._inner_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.OCR_MAX_WORKERS * PAGE_INFERENCE_WORKERS, 
            thread_name_prefix=INNER_THREAD_PREFIX
        )

    def initialize(self):
        """AI 엔진(RapidOCR) 및 레이아웃 서비스 초기화"""
        if self._engine is not None:
            return

        try:
            self._engine = RapidOCR(
                params={
                    "Global.use_cls": settings.USE_CLS,
                    "Det.model_path": settings.DET_MODEL_PATH,
                    "Rec.model_path": settings.REC_MODEL_PATH,
                    "Cls.model_path": settings.CLS_MODEL_PATH,
                    "Rec.keys_path": settings.KEYS_PATH,
                    "Det.db_thresh": settings.OCR_DET_DB_THRESH,
                    "Det.db_box_thresh": settings.OCR_DET_BOX_THRESH,
                    "Det.unclip_ratio": settings.OCR_DET_UNCLIP_RATIO,
                    "Det.limit_side_len": settings.OCR_DET_LIMIT_SIDE_LEN,
                }
            )
            layout_service.initialize()
            logger.info("OCR/Layout 엔진 로드 완료")
        except Exception as e:
            logger.error(f"엔진 초기화 실패: {e}")
            raise

    def shutdown(self):
        """서버 종료 시 모든 스레드 풀 리소스 해제"""
        self._inner_executor.shutdown(wait=True)
        self._executor.shutdown(wait=True)

    @property
    def engine(self) -> RapidOCR:
        """엔진 객체 지연 로딩 (Lazy Loading)"""
        if self._engine is None:
            self.initialize()
        if self._engine is None:
            raise RuntimeError("엔진 연결 실패")
        return self._engine

    def _process_single_page(
        self, page_img: Image.Image, page_num: int, filename: str
    ) -> PageResult:
        """단일 페이지 분석: Layout과 OCR을 병렬로 실행하여 속도 최적화"""
        try:
            # OpenCV 형식으로 변환
            img_rgb = page_img.convert("RGB")
            img_bgr = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2BGR)

            # 미리 생성된 내부 스레드 풀을 사용하여 병렬 추론 실행
            f_layout = self._inner_executor.submit(layout_service.infer, img_bgr)
            f_ocr = self._inner_executor.submit(self.engine, img_bgr)
            
            layout_out = f_layout.result()
            ocr_raw = f_ocr.result()

            # OCR 결과 데이터 정규화
            ocr_out = ocr_raw[0] if isinstance(ocr_raw, tuple) else ocr_raw
            txts, boxes = self._normalize_ocr_result(ocr_out)

            # 레이아웃 매핑 및 시각화 이미지 생성
            layout_regions = layout_service.analyze_and_save(
                img_bgr, boxes, txts, filename=filename, page_num=page_num, layout_out=layout_out
            )

            # 구조화 데이터 파싱 시도
            structured = parser_service.parse(boxes, txts)
            if structured:
                return PageResult(page_num=page_num, type=PageType.STRUCTURED, data=structured)

            # 구조화 실패 시 레이아웃 정보 반환
            if layout_regions:
                return PageResult(page_num=page_num, type=PageType.RAW, data=RawPageData(layout_regions))

            # 최종 폴백: 일반 OCR 텍스트 목록 반환
            return PageResult(page_num=page_num, type=PageType.RAW, data=self._get_box_fallback(txts, boxes))

        except Exception as e:
            logger.exception(f"P{page_num} 처리 실패: {e}")
            return PageResult(page_num=page_num, type=PageType.ERROR, data=ErrorPageData(message=str(e)))

    def _normalize_ocr_result(self, result: Any) -> Tuple[List[str], List[List[int]]]:
        """RapidOCROutput 객체 또는 리스트 형태의 결과를 표준 포맷으로 변환"""
        if not result:
            return [], []

        # 1. 속성 기반 접근 (RapidOCROutput 객체 대응)
        if hasattr(result, "txts") and hasattr(result, "boxes"):
            txts = list(result.txts)
            boxes = []
            for b in result.boxes:
                # numpy array인 경우 리스트로 변환 및 평탄화
                b_list = b.tolist() if hasattr(b, "tolist") else b
                boxes.append([int(v) for pt in b_list for v in pt])
            return txts, boxes

        # 2. 리스트 기반 접근 (구형 또는 리스트 반환 설정 대응)
        txts, boxes = [], []
        try:
            for item in result:
                if not item or len(item) < 2: continue
                flat_box = [int(v) for pt in item[0] for v in pt]
                boxes.append(flat_box)
                txts.append(str(item[1]))
        except (TypeError, IndexError) as e:
            logger.error(f"OCR 결과 정규화 실패: {e}")
            
        return txts, boxes

    def _get_box_fallback(self, txts: List[str], boxes: List[List[int]]) -> RawPageData:
        """레이아웃 분석이 불가능한 경우 텍스트와 좌표만 나열하여 반환"""
        content = []
        for t, b in zip(txts, boxes):
            x_coords, y_coords = b[0::2], b[1::2]
            xmin, ymin = min(x_coords), min(y_coords)
            content.append(OCRContent(
                text=t,
                box=OCRBox(x=xmin, y=ymin, w=max(x_coords) - xmin, h=max(y_coords) - ymin)
            ))
        return RawPageData(content)

    def _iter_pages(
        self, image: Image.Image, target_pages: Optional[Sequence[int]] = None
    ) -> Generator[Tuple[Image.Image, int], None, None]:
        """분석 대상 페이지 이미지를 안전하게 복사하여 생성"""
        for i, page in enumerate(ImageSequence.Iterator(image)):
            page_num = i + 1
            if target_pages and page_num not in target_pages: continue
            yield page.copy(), page_num

    async def process_image_async(
        self, image: Image.Image, filename: str, target_pages: Optional[Sequence[int]] = None
    ) -> Dict[str, Any]:
        """비동기 병렬 처리: FastAPI의 async 엔드포인트에서 호출"""
        layout_service.clear_debug_directory(filename)
        loop = asyncio.get_running_loop()

        tasks = [
            loop.run_in_executor(self._executor, self._process_single_page, p_img, p_num, filename)
            for p_img, p_num in self._iter_pages(image, target_pages)
        ]

        if not tasks: return {"filename": filename, "pages": []}
        results = await asyncio.gather(*tasks)
        return {"filename": filename, "pages": sorted(results, key=lambda x: x.page_num)}

    def process_image_generator(
        self, image: Image.Image, filename: str, target_pages: Optional[Sequence[int]] = None
    ) -> Generator[PageResult, None, None]:
        """스트리밍 처리: 분석 완료된 페이지부터 즉시 전송"""
        layout_service.clear_debug_directory(filename)
        for p_img, p_num in self._iter_pages(image, target_pages):
            yield self._process_single_page(p_img, p_num, filename)

    def process_image(self, image: Image.Image, filename: str, target_pages: Optional[Sequence[int]] = None) -> Dict[str, Any]:
        """동기 인터페이스: 일반적인 동기 호출 대응"""
        layout_service.clear_debug_directory(filename)
        try:
            asyncio.get_running_loop()
            page_data = list(self._iter_pages(image, target_pages))
            futures = [self._executor.submit(self._process_single_page, img, num, filename) for img, num in page_data]
            results = [f.result() for f in futures]
            return {"filename": filename, "pages": sorted(results, key=lambda x: x.page_num)}
        except RuntimeError:
            return asyncio.run(self.process_image_async(image, filename, target_pages))


ocr_service = OCRProcessor()
