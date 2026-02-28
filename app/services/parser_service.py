"""
텍스트 데이터를 분석하여 주요 항목별로 구조화하는 서비스
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from .utils import merge_boxes_into_lines, is_fuzzy_match, sanitize_ocr_text
from app.core.constants import (
    Patterns,
    Thresholds,
    DocKeyword,
    FieldKey,
    TextTag,
    PARSING_ORDER,
    SINGLE_LINE_KEYS,
)
from app.schemas.ocr import StructuredPageData

logger = logging.getLogger(__name__)


class StructuredParser:
    """텍스트 행들을 분석하여 법원, 사건, 당사자 등을 추출"""

    def parse(
        self, boxes: List[List[int]], txts: List[str]
    ) -> Optional[StructuredPageData]:
        """OCR 결과물(좌표, 텍스트)을 구조화된 데이터 객체로 변환"""
        if not boxes or not txts:
            return None

        # 텍스트 라인 병합
        text_lines = merge_boxes_into_lines(boxes, txts)

        # 문서 헤더(법원명, 결정문 여부) 위치 확인
        header_idx, sub_header_idx = self._detect_headers(text_lines)
        if header_idx == -1 or sub_header_idx == -1:
            return None

        # 주요 섹션별 데이터 추출 (사건, 채권자 등)
        start_idx = sub_header_idx + 1
        extracted_raw = self._extract_sections(text_lines, start_idx)

        # 상단 법원명 추출
        org_info = text_lines[header_idx]
        org_name = sanitize_ocr_text(str(org_info[FieldKey.TEXT]))

        # 최종 데이터 포맷팅
        formatted_data = self._format_data(extracted_raw, org_name)
        try:
            return StructuredPageData(**formatted_data)
        except Exception as e:
            logger.error(f"구조화 데이터 생성 실패: {e}")
            return None

    def _detect_headers(self, lines: List[Dict[str, Any]]) -> Tuple[int, int]:
        """문서 상단에서 법원 및 결정문 제목 위치 탐색"""
        h1_idx = h2_idx = -1
        limit = min(Thresholds.HEADER_SEARCH_LIMIT, len(lines))

        # 법원명 탐색 (상단 일정 범위 이내)
        for i in range(min(Thresholds.ORG_SEARCH_LIMIT, limit)):
            if re.search(Patterns.HEADER_MAIN, str(lines[i].get(FieldKey.TEXT, ""))):
                h1_idx = i
                break

        # 결정문 헤더 탐색 (법원명 발견 후 일정 범위 이내)
        if h1_idx != -1:
            for i in range(h1_idx + 1, min(h1_idx + Thresholds.SUB_HEADER_OFFSET, limit)):
                if re.search(Patterns.HEADER_SUB, str(lines[i].get(FieldKey.TEXT, ""))):
                    h2_idx = i
                    break
        return h1_idx, h2_idx

    def _extract_sections(
        self, lines: List[Dict[str, Any]], start_idx: int
    ) -> Dict[str, List[str]]:
        """순차적 키워드 매칭을 통해 섹션별 내용 수집"""
        parsed: Dict[str, List[str]] = {}
        target_keys = PARSING_ORDER
        curr_key_idx = 0
        buffer: List[str] = []
        curr_key: Optional[DocKeyword] = None

        for i in range(start_idx, len(lines)):
            line = lines[i]
            text = str(line.get(FieldKey.TEXT, ""))
            
            # 다음 목표 키워드 탐색
            found_key, found_idx = self._find_next_keyword(
                text, target_keys, curr_key_idx
            )

            if found_key:
                # 이전까지 쌓인 내용을 저장
                if curr_key:
                    parsed[curr_key.value] = buffer
                
                # 상태 업데이트
                curr_key, curr_key_idx, buffer = found_key, found_idx + 1, []
                
                # 키워드 뒤에 붙은 텍스트가 있으면 버퍼에 추가
                val_text = self._remove_keyword(text, found_key.value)
                if val_text:
                    buffer.append(val_text)
                continue

            if curr_key:
                # 종료 조건(날짜 등) 확인 시 중단
                if self._is_terminator(lines, i):
                    break
                
                cleaned = sanitize_ocr_text(text)
                if cleaned:
                    buffer.append(cleaned)

        # 마지막 세션 저장
        if curr_key:
            parsed[curr_key.value] = buffer
        return parsed

    def _find_next_keyword(
        self, text: str, keys: List[DocKeyword], start_idx: int
    ) -> Tuple[Optional[DocKeyword], int]:
        """텍스트에서 다음 순서의 키워드가 존재하는지 확인"""
        for idx in range(start_idx, len(keys)):
            if is_fuzzy_match(text, keys[idx].value):
                return keys[idx], idx
        return None, -1

    def _is_terminator(self, lines: List[Dict[str, Any]], idx: int) -> bool:
        """문서 하단 정보나 큰 공백을 기준으로 분석 종료 여부 판단"""
        line = lines[idx]
        # 날짜 패턴 감지 시 종료
        if re.search(Patterns.DATE_TERMINATOR, str(line.get(FieldKey.TEXT, ""))):
            return True
        
        # 이전 행과의 간격이 너무 크면 분석 중단
        if idx > 0:
            prev = lines[idx - 1]
            gap = float(line.get(FieldKey.Y_MIN, 0)) - float(prev.get(FieldKey.Y_MAX, 0))
            if gap > Thresholds.SECTION_GAP_LIMIT:
                return True
        return False

    def _remove_keyword(self, text: str, keyword_val: str) -> str:
        """텍스트에서 식별된 키워드(예: '사건')를 제거하고 내용만 추출"""
        pattern = r"[^가-힣a-zA-Z]*".join([re.escape(c) for c in list(keyword_val)])
        match = re.search(pattern, text)
        val = text[match.end() :] if match else text
        
        # 정규식 실패 시 직접 치환 시도
        if not match:
            for c in keyword_val:
                val = val.replace(c, "", 1)
        
        # 앞쪽의 특수문자나 공백 정리
        return sanitize_ocr_text(re.sub(r"^[\s:.]+", "", val).strip())

    def _format_data(self, data: Dict[str, List[str]], org_name: str) -> Dict[str, Any]:
        """수집된 세션별 텍스트 리스트를 최종 데이터 구조로 가공"""
        final: Dict[str, Any] = {DocKeyword.ORG.value: org_name}
        
        for k, items in data.items():
            if not items:
                continue
            
            # 단일 문장 항목 (병합 처리)
            if k in SINGLE_LINE_KEYS:
                final[k] = TextTag.SPACE.value.join(items).strip()
            else:
                # 목록형 데이터 (번호 기준 분리 시도)
                full = TextTag.SPACE.value.join(items)
                split = re.sub(
                    Patterns.LIST_ITEM,
                    lambda m: TextTag.SPLIT.value + m.group(1),
                    full,
                )
                
                if TextTag.SPLIT.value in split:
                    parts = [
                        p.strip() for p in split.split(TextTag.SPLIT.value) if p.strip()
                    ]
                    final[k] = parts if len(parts) > 1 else (parts[0] if parts else "")
                else:
                    final[k] = full
        return final


parser_service = StructuredParser()
