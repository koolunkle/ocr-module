"""
OCR 및 문서 분석 통합 서비스
"""

import logging
import asyncio
import concurrent.futures
from typing import Any, Dict, Generator, Optional, List, Tuple, Sequence

import cv2
import numpy as np
from PIL import Image, ImageSequence
from rapidocr import RapidOCR

from app.core.config import settings
from app.core.constants import PageType, FieldKey
from app.schemas.ocr import PageResult, RawPageData, ErrorPageData, OCRContent, OCRBox
from app.services.parser_service import parser_service
from app.services.layout_service import layout_service

logger = logging.getLogger(__name__)


class OCRService:
    """RapidOCR/Layout 엔진을 활용한 문서 처리 파이프라인"""

    def __init__(self):
        self._engine: Optional[RapidOCR] = None
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.OCR_MAX_WORKERS, thread_name_prefix="OCRWorker"
        )

    def initialize(self):
        """AI 엔진 초기화"""
        if self._engine is None:
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
                raise e

    def shutdown(self):
        """리소스 해제"""
        self._executor.shutdown(wait=True)

    @property
    def engine(self) -> RapidOCR:
        if self._engine is None:
            self.initialize()
        if self._engine is None:
            raise RuntimeError("엔진 연결 실패")
        return self._engine

    def _process_single_page(self, args: Tuple[Image.Image, int, Optional[str]]) -> PageResult:
        """페이지 분석 파이프라인 (Layout -> OCR -> Merge)"""
        page_img, page_num, filename = args
        try:
            # 이미지 변환
            img_bgr = cv2.cvtColor(np.array(page_img.convert("RGB")), cv2.COLOR_RGB2BGR)
            
            # 1. 레이아웃 추론 (구조 파악)
            layout_out = layout_service.infer(img_bgr, page_num)
            
            # 2. OCR 수행 (텍스트 인식)
            ocr_out = self.engine(img_bgr)
            txts, boxes = self._parse_ocr_result(ocr_out)

            # 3. 레이아웃 매핑 및 시각화 저장
            layout_regions = layout_service.analyze_and_save(
                img_bgr, boxes, txts, filename=filename, page_num=page_num, layout_out=layout_out
            )

            # 4. 결과 우선순위 결정 (Structured -> Layout-Raw -> Box-Raw)
            # 비즈니스 데이터 추출 시도
            structured = parser_service.parse(boxes, txts)
            if structured:
                return PageResult(page_num=page_num, type=PageType.STRUCTURED, data=structured)

            # 레이아웃 기반 결과 반환
            if layout_regions:
                return PageResult(page_num=page_num, type=PageType.RAW, data=RawPageData(layout_regions))

            # 폴백: 단순 텍스트 박스 나열
            return PageResult(page_num=page_num, type=PageType.RAW, data=self._get_box_fallback(txts, boxes))

        except Exception as e:
            logger.error(f"P{page_num} 처리 오류: {e}")
            return PageResult(page_num=page_num, type=PageType.ERROR, data=ErrorPageData(message=str(e)))

    def _parse_ocr_result(self, result: Any) -> Tuple[List[str], List[List[int]]]:
        """OCR 결과 정규화"""
        if not result:
            return [], []
        
        # 속성 존재 여부 확인 
        txts_attr = getattr(result, "txts", None)
        boxes_attr = getattr(result, "boxes", None)

        if txts_attr is not None and boxes_attr is not None:
            return list(txts_attr), [[int(v) for sub in b.tolist() for v in sub] for b in boxes_attr]
        
        items = result[0] if isinstance(result, list) and result and result[0] else []
        txts, boxes = [], []
        for item in items:
            boxes.append([int(v) for sub in item[0] for v in sub])
            txts.append(str(item[1]))
        return txts, boxes

    def _get_box_fallback(self, txts: List[str], boxes: List[List[int]]) -> RawPageData:
        """단순 텍스트 목록 생성"""
        content = []
        for t, b in zip(txts, boxes):
            x_coords, y_coords = b[0::2], b[1::2]
            xmin, ymin = min(x_coords), min(y_coords)
            content.append(OCRContent(
                text=t,
                box=OCRBox(x=xmin, y=ymin, w=max(x_coords) - xmin, h=max(y_coords) - ymin)
            ))
        return RawPageData(content)

    async def process_image_async(
        self, image: Image.Image, filename: str, target_pages: Optional[Sequence[int]] = None
    ) -> Dict[str, Any]:
        """비동기 병렬 처리"""
        layout_service.clear_debug_directory(filename)
        
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self._executor, self._process_single_page, (page.copy(), i + 1, filename))
            for i, page in enumerate(ImageSequence.Iterator(image))
            if not target_pages or (i + 1) in target_pages
        ]

        if not tasks:
            return {"filename": filename, "pages": []}

        results = await asyncio.gather(*tasks)
        return {"filename": filename, "pages": sorted(results, key=lambda x: x.page_num)}

    def process_image_generator(
        self, image: Image.Image, filename: str, target_pages: Optional[Sequence[int]] = None
    ) -> Generator[PageResult, None, None]:
        """스트리밍 처리"""
        layout_service.clear_debug_directory(filename)
        for i, page in enumerate(ImageSequence.Iterator(image)):
            p_num = i + 1
            if target_pages and p_num not in target_pages:
                continue
            yield self._process_single_page((page, p_num, filename))

    def process_image(self, *args, **kwargs) -> Dict[str, Any]:
        """동기 인터페이스 (FastAPI 대응)"""
        img, fname = args[0], args[1]
        layout_service.clear_debug_directory(fname)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                t_pages = args[2] if len(args) > 2 else None
                tasks = [
                    (page.copy(), i + 1, fname)
                    for i, page in enumerate(ImageSequence.Iterator(img))
                    if not t_pages or (i + 1) in t_pages
                ]
                results = list(self._executor.map(self._process_single_page, tasks))
                return {"filename": fname, "pages": sorted(results, key=lambda x: x.page_num)}
        except RuntimeError:
            pass
        return asyncio.run(self.process_image_async(*args, **kwargs))


ocr_service = OCRService()
