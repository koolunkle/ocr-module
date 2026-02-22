"""
추출된 텍스트를 구조화된 데이터로 변환하는 서비스
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from .utils import merge_boxes_into_lines, is_fuzzy_match, sanitize_ocr_text
from app.core.constants import (
    Patterns,
    Thresholds,
    Keyword,
    FieldKey,
    Tags,
    STRUCTURED_PARSING_KEYS,
    SIMPLE_TEXT_KEYS,
)
from app.schemas.ocr import StructuredPageData

logger = logging.getLogger(__name__)


class StructuredParser:
    """텍스트 블록에서 주요 키워드 기반 세션을 추출하여 구조화합니다."""

    def parse(
        self, boxes: List[List[int]], txts: List[str]
    ) -> Optional[StructuredPageData]:
        if not boxes or not txts:
            return None

        # 1. 라인 병합
        text_lines = merge_boxes_into_lines(boxes, txts)

        # 2. 문서 유형(헤더) 감지
        header_idx, sub_header_idx = self._detect_headers(text_lines)
        if header_idx == -1 or sub_header_idx == -1:
            return None

        # 3. 섹션 데이터 추출
        start_idx = sub_header_idx + 1
        extracted_raw = self._extract_sections(text_lines, start_idx)

        # 상단 기관 정보 추출
        org_info = text_lines[header_idx]
        org_name = sanitize_ocr_text(str(org_info[FieldKey.TEXT.value]))

        # 4. 모델 데이터 생성
        formatted_data = self._format_data(extracted_raw, org_name)
        try:
            return StructuredPageData(**formatted_data)
        except Exception as e:
            logger.error(f"구조화 데이터 생성 실패: {e}")
            return None

    def _detect_headers(self, lines: List[Dict[str, Any]]) -> Tuple[int, int]:
        """문서 상단에서 핵심 헤더 위치 탐색"""
        h1_idx = h2_idx = -1
        limit = min(10, len(lines))

        for i in range(min(5, limit)):
            if re.search(
                Patterns.HEADER_MAIN, str(lines[i].get(FieldKey.TEXT.value, ""))
            ):
                h1_idx = i
                break

        if h1_idx != -1:
            for i in range(h1_idx + 1, min(h1_idx + 4, limit)):
                if re.search(
                    Patterns.HEADER_SUB, str(lines[i].get(FieldKey.TEXT.value, ""))
                ):
                    h2_idx = i
                    break
        return h1_idx, h2_idx

    def _extract_sections(
        self, lines: List[Dict[str, Any]], start_idx: int
    ) -> Dict[str, List[str]]:
        """키워드 매칭을 통한 섹션별 텍스트 수집"""
        parsed: Dict[str, List[str]] = {}
        target_keys = STRUCTURED_PARSING_KEYS
        curr_key_idx = 0
        buffer: List[str] = []
        curr_key: Optional[Keyword] = None

        for i in range(start_idx, len(lines)):
            line = lines[i]
            text = str(line.get(FieldKey.TEXT.value, ""))
            found_key, found_idx = self._find_next_keyword(
                text, target_keys, curr_key_idx
            )

            if found_key:
                if curr_key:
                    parsed[curr_key.value] = buffer
                curr_key, curr_key_idx, buffer = found_key, found_idx + 1, []
                val_text = self._remove_keyword(text, found_key.value)
                if val_text:
                    buffer.append(val_text)
                continue

            if curr_key:
                if self._is_terminator(lines, i):
                    break
                cleaned = sanitize_ocr_text(text)
                if cleaned:
                    buffer.append(cleaned)

        if curr_key:
            parsed[curr_key.value] = buffer
        return parsed

    def _find_next_keyword(
        self, text: str, keys: List[Keyword], start_idx: int
    ) -> Tuple[Optional[Keyword], int]:
        for idx in range(start_idx, len(keys)):
            if is_fuzzy_match(text, keys[idx].value):
                return keys[idx], idx
        return None, -1

    def _is_terminator(self, lines: List[Dict[str, Any]], idx: int) -> bool:
        """파싱 종료 조건(날짜 패턴 또는 큰 공백) 확인"""
        line = lines[idx]
        if re.search(Patterns.TERMINATOR_DATE, str(line.get(FieldKey.TEXT.value, ""))):
            return True
        if idx > 0:
            prev = lines[idx - 1]
            gap = float(line.get(FieldKey.Y_MIN.value, 0)) - float(
                prev.get(FieldKey.Y_MAX.value, 0)
            )
            if gap > Thresholds.SECTION_GAP_LIMIT:
                return True
        return False

    def _remove_keyword(self, text: str, keyword_val: str) -> str:
        """텍스트 내에서 식별된 키워드 제거"""
        pattern = r"[^가-힣a-zA-Z]*".join([re.escape(c) for c in list(keyword_val)])
        match = re.search(pattern, text)
        val = text[match.end() :] if match else text
        if not match:
            for c in keyword_val:
                val = val.replace(c, "", 1)
        return sanitize_ocr_text(re.sub(r"^[\s:.]+", "", val).strip())

    def _format_data(self, data: Dict[str, List[str]], org_name: str) -> Dict[str, Any]:
        """수집된 데이터를 최종 스키마 구조로 정리"""
        final: Dict[str, Any] = {Keyword.ORG.value: org_name}
        for k, items in data.items():
            if not items:
                continue
            if k in SIMPLE_TEXT_KEYS:
                final[k] = Tags.SPACE.value.join(items).strip()
            else:
                full = Tags.SPACE.value.join(items)
                split = re.sub(
                    Patterns.LIST_ITEM_SPLIT,
                    lambda m: Tags.SPLIT.value + m.group(1),
                    full,
                )
                if Tags.SPLIT.value in split:
                    parts = [
                        p.strip() for p in split.split(Tags.SPLIT.value) if p.strip()
                    ]
                    final[k] = parts if len(parts) > 1 else (parts[0] if parts else "")
                else:
                    final[k] = full
        return final


parser_service = StructuredParser()
