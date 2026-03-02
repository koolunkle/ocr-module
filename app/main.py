"""
[메인] FastAPI 애플리케이션 진입점
역할: 전체 서버의 생명주기(Lifespan) 관리 및 API 라우터를 등록합니다.
"""

import logging
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI

from app.api import endpoints as ocr
from app.config import settings
from app.engine.processor import ocr_service

# --- 지역 상수 (Local Constants) ---
DEFAULT_HOST: Final = "0.0.0.0"
DEFAULT_PORT: Final = 8000

# 애플리케이션 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버의 시작과 종료 시점에 실행되는 이벤트 핸들러
    - 시작 시: 엔진 초기화 및 로그 출력
    - 종료 시: 스레드 풀 정리 등 자원 해제
    """
    logger.info("=" * 50)
    logger.info(f"애플리케이션 시작: {settings.PROJECT_NAME}")
    logger.info(f"설정 로드됨:")
    logger.info(f" - 엔진 자원: CPU 워커 {settings.OCR_MAX_WORKERS}개 사용")
    logger.info(f" - 디버그 모드: {'활성화' if settings.DEBUG else '비활성화'}")
    logger.info("=" * 50)

    # 딥러닝 엔진(OCR, Layout) 사전 로드 및 초기화
    ocr_service.initialize()

    yield

    # 애플리케이션 종료 시 안전하게 리소스 반납
    ocr_service.shutdown()
    logger.info("서비스 종료 및 자원 해제 완료.")


# FastAPI 인스턴스 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="RapidOCR 및 RapidLayout을 활용한 문서 분석 API 서비스",
    version="1.1.0",
    lifespan=lifespan
)

# API 라우터 등록 (기본 경로: /api/v1/ocr)
app.include_router(ocr.router, prefix=f"{settings.API_V1_STR}/ocr", tags=["OCR 서비스"])


@app.get("/", tags=["상태 관리"])
def root():
    """서버 구동 상태 확인용 루트 엔드포인트"""
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "api_path": f"{settings.API_V1_STR}/ocr"
    }


if __name__ == "__main__":
    # 로컬 테스트 및 직접 실행 시 uvicorn 구동
    import uvicorn
    uvicorn.run("app.main:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=True)
