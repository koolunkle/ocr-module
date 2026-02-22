"""
OCR 엔진 관리 및 이미지 처리 서비스
"""

import os
import logging
import concurrent.futures
from typing import Any, Dict, Generator, Optional, List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageSequence
from rapidocr import RapidOCR

from app.core.config import settings
from app.core.constants import PageType
from app.schemas.ocr import PageResult, RawPageData, ErrorPageData
from app.services.parser_service import parser_service

logger = logging.getLogger(__name__)


class OCRService:
    """RapidOCR을 사용하여 이미지에서 텍스트를 추출하고 구조화합니다."""

    def __init__(self):
        self._engine: Any = None
        # 전역적으로 사용할 스레드 풀 생성
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=os.cpu_count() or 4, thread_name_prefix="OCRWorker"
        )

    def initialize(self):
        """엔진 초기화 및 모델 로드"""
        if self._engine is None:
            logger.info("OCR 엔진 초기화 중...")
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
                logger.info("OCR 엔진 초기화 완료")
            except Exception as e:
                logger.error(f"OCR 엔진 초기화 실패: {e}")
                raise e

    def shutdown(self):
        """리소스 정리 및 스레드 풀 종료"""
        logger.info("OCR 서비스 스레드 풀 종료 중...")
        self._executor.shutdown(wait=True)

    @property
    def engine(self):
        if self._engine is None:
            self.initialize()
        return self._engine

    def _process_single_page(self, args: Tuple[Image.Image, int]) -> PageResult:
        """단일 페이지 OCR 및 파싱 처리"""
        page_img, page_num = args
        try:
            img_bgr = cv2.cvtColor(np.array(page_img.convert("RGB")), cv2.COLOR_RGB2BGR)
            result = self.engine(img_bgr)

            raw_txts, raw_boxes = [], []
            if result:
                if hasattr(result, "txts"):
                    raw_txts = list(result.txts)
                    raw_boxes = [
                        [int(v) for sub in b.tolist() for v in sub]
                        for b in result.boxes
                    ]
                elif isinstance(result, list) and result[0]:
                    for item in result[0]:
                        raw_boxes.append([int(v) for sub in item[0] for v in sub])
                        raw_txts.append(str(item[1]))

            # 구조화 분석 시도
            structured_data = parser_service.parse(raw_boxes, raw_txts)

            if structured_data:
                return PageResult(
                    page_num=page_num, type=PageType.STRUCTURED, data=structured_data
                )

            # Raw 데이터 포맷팅 (x, y, w, h 형식)
            content_items = []
            for i in range(len(raw_txts)):
                box = raw_boxes[i]
                # box: [x1, y1, x2, y2, x3, y3, x4, y4] 또는 [x_min, y_min, x_max, y_max]
                if len(box) == 8:
                    x_min = min(box[0], box[2], box[4], box[6])
                    y_min = min(box[1], box[3], box[5], box[7])
                    x_max = max(box[0], box[2], box[4], box[6])
                    y_max = max(box[1], box[3], box[5], box[7])
                else:
                    x_min, y_min, x_max, y_max = box[0], box[1], box[2], box[3]

                content_items.append(
                    {
                        "text": raw_txts[i],
                        "box": {
                            "x": x_min,
                            "y": y_min,
                            "w": x_max - x_min,
                            "h": y_max - y_min,
                        },
                    }
                )

            return PageResult(
                page_num=page_num,
                type=PageType.RAW,
                data=RawPageData(content=content_items),
            )

        except Exception as e:
            logger.error(f"{page_num}페이지 처리 실패: {e}")
            return PageResult(
                page_num=page_num,
                type=PageType.ERROR,
                data=ErrorPageData(message=str(e)),
            )

    def process_image_generator(
        self,
        image: Image.Image,
        filename: str,
        target_pages: Optional[List[int]] = None,
    ) -> Generator[PageResult, None, None]:
        """스트리밍 처리를 위한 제너레이터"""
        for i, page_img in enumerate(ImageSequence.Iterator(image)):
            p_num = i + 1
            if target_pages and p_num not in target_pages:
                continue
            yield self._process_single_page((page_img, p_num))

    def process_image(
        self,
        image: Image.Image,
        filename: str,
        target_pages: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """병렬 처리를 이용한 일괄 OCR 수행"""
        tasks = []
        for i, page_img in enumerate(ImageSequence.Iterator(image)):
            p_num = i + 1
            if target_pages and p_num not in target_pages:
                continue
            tasks.append((page_img.copy(), p_num))

        if not tasks:
            return {"filename": filename, "pages": []}

        # [수정] with 문을 제거하여 스레드 풀이 종료되지 않게 함
        results = list(self._executor.map(self._process_single_page, tasks))

        results.sort(key=lambda x: x.page_num)
        return {"filename": filename, "pages": results}


ocr_service = OCRService()
