"""
OCR 엔진 구동 및 이미지/문서 처리 서비스
"""

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
    """RapidOCR 엔진을 사용한 이미지 텍스트 추출 및 구조화"""

    def __init__(self):
        self._engine: Any = None
        # 병렬 처리를 위한 스레드 풀
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.OCR_MAX_WORKERS, thread_name_prefix="OCRWorker"
        )

    def initialize(self):
        """엔진 설정 로드 및 초기화"""
        if self._engine is None:
            logger.info("OCR 엔진 초기화 시작...")
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
        """스레드 풀 리소스 정리"""
        logger.info("OCR 서비스 종료 및 스레드 풀 정리...")
        self._executor.shutdown(wait=True)

    @property
    def engine(self):
        """엔진 인스턴스 지연 로딩"""
        if self._engine is None:
            self.initialize()
        return self._engine

    def _process_single_page(self, args: Tuple[Image.Image, int]) -> PageResult:
        """단일 페이지에 대한 OCR 및 데이터 분석 수행"""
        page_img, page_num = args
        try:
            # PIL 이미지를 OpenCV(BGR) 포맷으로 변환
            img_bgr = cv2.cvtColor(np.array(page_img.convert("RGB")), cv2.COLOR_RGB2BGR)
            result = self.engine(img_bgr)

            raw_txts, raw_boxes = [], []
            if result:
                # 결과 포맷 대응 
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

            # 1. 구조화 분석 시도 (사건 등 추출)
            structured_data = parser_service.parse(raw_boxes, raw_txts)

            if structured_data:
                return PageResult(
                    page_num=page_num, type=PageType.STRUCTURED, data=structured_data
                )

            # 2. 구조화 실패 시 일반 텍스트 데이터(Raw) 반환
            content_items = []
            for i in range(len(raw_txts)):
                box = raw_boxes[i]
                # 좌표 포맷 정규화 [x, y, w, h]
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
        """페이지별 순차 처리를 위한 제너레이터 (스트리밍 응답용)"""
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
        """병렬 처리를 이용한 이미지 전체 일괄 처리"""
        tasks = []
        for i, page_img in enumerate(ImageSequence.Iterator(image)):
            p_num = i + 1
            if target_pages and p_num not in target_pages:
                continue
            tasks.append((page_img.copy(), p_num))

        if not tasks:
            return {"filename": filename, "pages": []}

        # 스레드 풀을 이용한 병렬 실행
        results = list(self._executor.map(self._process_single_page, tasks))

        results.sort(key=lambda x: x.page_num)
        return {"filename": filename, "pages": results}


ocr_service = OCRService()
