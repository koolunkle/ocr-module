"""
문서 레이아웃 분석 및 영역별 데이터 매핑 서비스
"""

import logging
import os
import shutil
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2
from rapid_layout import RapidLayout

from app.core.config import settings
from app.core.constants import (
    FieldKey, Thresholds, LAYOUT_COLORS, DEFAULT_LAYOUT_COLOR, VIS_DIR
)
from app.schemas.ocr import LayoutRegion, OCRBox
from app.services.utils import merge_boxes_into_lines

logger = logging.getLogger(__name__)


class LayoutService:
    """RapidLayout 엔진 관리 및 시각화/매핑 로직 제공"""

    def __init__(self):
        self._engine: Optional[RapidLayout] = None

    def initialize(self):
        """엔진 설정 및 로드"""
        if self._engine is None:
            try:
                self._engine = RapidLayout(
                    model_path=settings.LAYOUT_MODEL_PATH,
                    dict_path=settings.LAYOUT_DICT_PATH,
                )
                logger.info("레이아웃 엔진 초기화 완료")
            except Exception as e:
                logger.error(f"레이아웃 엔진 초기화 실패: {e}")
                raise e

    @property
    def engine(self) -> RapidLayout:
        if self._engine is None:
            self.initialize()
        if self._engine is None:
            raise RuntimeError("레이아웃 엔진 초기화 실패")
        return self._engine

    def get_safe_debug_dir(self, filename: Optional[str]) -> str:
        """파일명 기반 저장 경로 생성"""
        safe_folder = "unknown"
        if filename:
            base_name = os.path.splitext(filename)[0]
            safe_folder = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in base_name])
        return os.path.join(VIS_DIR, safe_folder)


    def clear_debug_directory(self, filename: Optional[str]):
        """작업 시작 전 기존 디버그 정보 초기화"""
        if not settings.DEBUG or not filename:
            return
        target_dir = self.get_safe_debug_dir(filename)
        if os.path.exists(target_dir):
            try:
                shutil.rmtree(target_dir)
            except Exception as e:
                logger.warning(f"디버그 폴더 초기화 실패: {e}")

    def infer(self, img: np.ndarray, page_num: Optional[int] = None) -> Any:
        """이미지 영역 추론"""
        return self.engine(img)

    def analyze_and_save(
        self, 
        img: np.ndarray, 
        raw_boxes: List[List[int]], 
        raw_txts: List[str],
        filename: Optional[str] = None,
        page_num: Optional[int] = None,
        layout_out: Optional[Any] = None
    ) -> List[LayoutRegion]:
        """분석 결과 매핑 및 보정된 시각화 이미지 저장"""
        try:
            out = layout_out if layout_out is not None else self.infer(img, page_num)
            boxes = getattr(out, "boxes", [])
            labels = getattr(out, "class_names", [])
            scores = getattr(out, "scores", [])

            # 시각화 캔버스 준비
            debug_canvas = img.copy() if settings.DEBUG else None
            overlay = img.copy() if settings.DEBUG else None

            # 매칭을 위한 OCR 데이터 가공
            ocr_items = self._prepare_ocr_data(raw_boxes, raw_txts)
            regions = []

            for bbox, label, score in zip(boxes, labels, scores):
                if score < settings.LAYOUT_SCORE_THRESHOLD:
                    continue

                # 4개 인자로 명시적 언패킹 
                m_xmin, m_ymin, m_xmax, m_ymax = map(int, bbox)
                matched_ocr = self._filter_ocr_in_bbox(ocr_items, (m_xmin, m_ymin, m_xmax, m_ymax))
                
                # 좌표 보정 및 텍스트 병합
                final_rect, matched_lines = self._process_region_data(bbox, matched_ocr)

                # 디버그 드로잉
                if debug_canvas is not None and overlay is not None:
                    self._draw_region(debug_canvas, overlay, final_rect, str(label), float(score))

                regions.append(LayoutRegion(
                    type=str(label), score=round(float(score), 4),
                    rect=final_rect, lines=matched_lines
                ))

            if debug_canvas is not None and overlay is not None:
                self._save_final_visual(debug_canvas, overlay, filename, page_num)

            return regions

        except Exception as e:
            logger.error(f"레이아웃 매핑 오류: {e}")
            return []

    def _prepare_ocr_data(self, boxes: List[List[int]], txts: List[str]) -> List[Dict[str, Any]]:
        """매칭 성능 향상을 위한 좌표 사전 계산"""
        data = []
        for b, t in zip(boxes, txts):
            b_np = np.array(b)
            data.append({
                "box": b, "text": t,
                "xmin": np.min(b_np[0::2]), "ymin": np.min(b_np[1::2]),
                "xmax": np.max(b_np[0::2]), "ymax": np.max(b_np[1::2]),
            })
        return data

    def _process_region_data(self, model_bbox: Any, matched_ocr: List[Dict[str, Any]]) -> Tuple[OCRBox, List[str]]:
        """영역 내 텍스트 병합 및 좌표 보정"""
        m_xmin, m_ymin, m_xmax, m_ymax = map(int, model_bbox)
        
        if not matched_ocr:
            return OCRBox(x=m_xmin, y=m_ymin, w=m_xmax - m_xmin, h=m_ymax - m_ymin), []

        # 텍스트 범위를 포함하도록 박스 확장
        f_xmin = int(min(min(i["xmin"] for i in matched_ocr), m_xmin))
        f_ymin = int(min(min(i["ymin"] for i in matched_ocr), m_ymin))
        f_xmax = int(max(max(i["xmax"] for i in matched_ocr), m_xmax))
        f_ymax = int(max(max(i["ymax"] for i in matched_ocr), m_ymax))
        
        # 영역 내 텍스트 라인 병합
        merged = merge_boxes_into_lines([i["box"] for i in matched_ocr], [i["text"] for i in matched_ocr])
        lines = [str(line[FieldKey.TEXT]) for line in merged]
        
        return OCRBox(x=f_xmin, y=f_ymin, w=f_xmax - f_xmin, h=f_ymax - f_ymin), lines

    def _draw_region(self, canvas: np.ndarray, overlay: np.ndarray, rect: OCRBox, label: str, score: float):
        """박스 및 라벨 시각화"""
        color = LAYOUT_COLORS.get(label, DEFAULT_LAYOUT_COLOR)
        # 영역 채우기
        cv2.rectangle(overlay, (rect.x, rect.y), (rect.x + rect.w, rect.y + rect.h), color, -1)
        # 테두리
        cv2.rectangle(canvas, (rect.x, rect.y), (rect.x + rect.w, rect.y + rect.h), color, 2)
        # 라벨 배경 및 텍스트
        txt = f"{label} {score:.2f}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(canvas, (rect.x, rect.y - th - 10), (rect.x + tw + 10, rect.y), color, -1)
        cv2.putText(canvas, txt, (rect.x + 5, rect.y - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    def _save_final_visual(self, canvas: np.ndarray, overlay: np.ndarray, filename: Optional[str], page_num: Optional[int]):
        """이미지 합성 및 파일 저장"""
        alpha = Thresholds.LAYOUT_VIS_ALPHA
        cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0, canvas)
        target_dir = self.get_safe_debug_dir(filename)
        os.makedirs(target_dir, exist_ok=True)
        cv2.imwrite(os.path.join(target_dir, f"layout_vis_p{page_num}.jpg"), canvas)

    def _filter_ocr_in_bbox(self, ocr_data: List[Dict[str, Any]], region_bbox: Tuple[int, int, int, int]) -> List[Dict[str, Any]]:
        """영역 중첩 기준 필터링"""
        rx_min, ry_min, rx_max, ry_max = region_bbox
        margin, ratio = Thresholds.LAYOUT_MATCH_MARGIN, Thresholds.LAYOUT_Y_OVERLAP_RATIO
        
        matched = []
        for item in ocr_data:
            overlap_h = max(0, min(ry_max + margin, item["ymax"]) - max(ry_min - margin, item["ymin"]))
            overlap_w = max(0, min(rx_max + margin, item["xmax"]) - max(rx_min - margin, item["xmin"]))
            if overlap_w > 0:
                line_h = item["ymax"] - item["ymin"]
                if line_h > 0 and (overlap_h / line_h >= ratio):
                    matched.append(item)
        return matched


layout_service = LayoutService()
