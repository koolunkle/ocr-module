"""
애플리케이션 전역 설정 및 환경 변수 관리
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 및 AI 모델 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"


class Settings(BaseSettings):
    """시스템 환경 변수 및 OCR 엔진 기본 설정"""

    PROJECT_NAME: str = Field(default="RapidOCR API Service", description="서비스 명칭")
    API_V1_STR: str = Field(default="/api/v1", description="API 버전 경로")

    # 엔진 모델 파일 경로 (ONNX)
    DET_MODEL_PATH: str = Field(default=str(MODELS_DIR / "ch_PP-OCRv4_det_infer.onnx"))
    REC_MODEL_PATH: str = Field(
        default=str(MODELS_DIR / "korean_PP-OCRv4_rec_infer.onnx")
    )
    CLS_MODEL_PATH: str = Field(
        default=str(MODELS_DIR / "ch_ppocr_mobile_v2.0_cls_infer.onnx")
    )
    KEYS_PATH: str = Field(default=str(MODELS_DIR / "korean_dict.txt"))

    # 레이아웃 분석 모델 설정
    LAYOUT_MODEL_PATH: str = Field(default=str(MODELS_DIR / "layout_cdla.onnx"))
    LAYOUT_DICT_PATH: str = Field(default=str(MODELS_DIR / "layout_dict.txt"))
    LAYOUT_SCORE_THRESHOLD: float = 0.5

    # OCR 엔진 파라미터
    OCR_DET_LIMIT_SIDE_LEN: int = 960
    OCR_DET_DB_THRESH: float = 0.3
    OCR_DET_BOX_THRESH: float = 0.5
    OCR_DET_UNCLIP_RATIO: float = 1.6
    USE_CLS: bool = False

    # 시스템 운영 설정
    OCR_MAX_WORKERS: int = Field(default=os.cpu_count() or 4)
    DEBUG: bool = Field(default=True, description="디버그 모드 (시각화 이미지 저장 등)")

    # 환경 변수 파일 (.env) 설정
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
