"""
애플리케이션 전역 설정 관리
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 및 모델 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"


class Settings(BaseSettings):
    """시스템 환경 변수 및 기본 설정"""

    PROJECT_NAME: str = Field(default="RapidOCR API Service", description="서비스 명칭")
    API_V1_STR: str = Field(default="/api/v1", description="API 버전 경로")

    # 엔진 모델 경로
    DET_MODEL_PATH: str = Field(default=str(MODELS_DIR / "ch_PP-OCRv4_det_infer.onnx"))
    REC_MODEL_PATH: str = Field(
        default=str(MODELS_DIR / "korean_PP-OCRv4_rec_infer.onnx")
    )
    CLS_MODEL_PATH: str = Field(
        default=str(MODELS_DIR / "ch_ppocr_mobile_v2.0_cls_infer.onnx")
    )
    KEYS_PATH: str = Field(default=str(MODELS_DIR / "korean_dict.txt"))

    # 알고리즘 파라미터
    OCR_DET_LIMIT_SIDE_LEN: int = 960
    OCR_DET_DB_THRESH: float = 0.3
    OCR_DET_BOX_THRESH: float = 0.5
    OCR_DET_UNCLIP_RATIO: float = 1.6
    USE_CLS: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
