"""
[설정] 애플리케이션 전역 환경 설정
역할: AI 모델 경로, 엔진 파라미터, 시스템 운영 설정을 관리하며 .env 파일을 지원합니다.
"""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 및 AI 모델 저장소 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"


class Settings(BaseSettings):
    """시스템 전역 설정 관리 객체 (BaseSettings 상속)"""

    PROJECT_NAME: str = Field(default="RapidOCR API Service", description="서비스 이름")
    APP_VERSION: str = Field(default="1.1.0", description="애플리케이션 버전")
    API_V1_STR: str = Field(default="/api/v1", description="API 기본 버전 경로")

    # --- OCR 모델 설정 (ONNX 파일 경로) ---
    DET_MODEL_PATH: str = Field(default=str(MODELS_DIR / "ch_PP-OCRv4_det_infer.onnx"))
    REC_MODEL_PATH: str = Field(default=str(MODELS_DIR / "korean_PP-OCRv4_rec_infer.onnx"))
    CLS_MODEL_PATH: str = Field(default=str(MODELS_DIR / "ch_ppocr_mobile_v2.0_cls_infer.onnx"))
    KEYS_PATH: str = Field(default=str(MODELS_DIR / "korean_dict.txt"))

    # --- 레이아웃 모델 설정 ---
    LAYOUT_MODEL_PATH: str = Field(default=str(MODELS_DIR / "layout_cdla.onnx"))
    LAYOUT_DICT_PATH: str = Field(default=str(MODELS_DIR / "layout_dict.txt"))
    LAYOUT_SCORE_THRESHOLD: float = 0.5  # 레이아웃 분석 신뢰도 임계값

    # --- OCR 엔진 세부 파라미터 ---
    OCR_DET_LIMIT_SIDE_LEN: int = 960
    OCR_DET_DB_THRESH: float = 0.3
    OCR_DET_BOX_THRESH: float = 0.5
    OCR_DET_UNCLIP_RATIO: float = 1.6
    USE_CLS: bool = False  # 텍스트 방향 보정 사용 여부

    # --- 시스템 자원 및 디버그 설정 ---
    OCR_MAX_WORKERS: int = Field(default=os.cpu_count() or 4)
    DEBUG: bool = Field(default=True, description="디버그 모드 (분석 결과 시각화 이미지 저장 등 활성화)")

    # 환경 변수 설정 파일 우선순위: .env -> .env.local -> 기본값
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
