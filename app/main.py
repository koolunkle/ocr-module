import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.routers import ocr
from app.core.config import settings
from app.services.ocr_service import ocr_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 설정 확인용 로그 출력
    logger.info("=" * 50)
    logger.info(f"Starting {settings.PROJECT_NAME}...")
    logger.info(f"Loaded Settings from .env or default:")
    logger.info(f" - DET_MODEL: {settings.DET_MODEL_PATH}")
    logger.info(f" - REC_MODEL: {settings.REC_MODEL_PATH}")
    logger.info(f" - USE_CLS: {settings.USE_CLS}")
    logger.info("=" * 50)

    # OCR 엔진 초기화
    ocr_service.initialize()

    yield

    # 서버 종료 시 스레드 풀 정리
    ocr_service.shutdown()
    logger.info("Service shutdown complete.")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# 라우터 등록
app.include_router(ocr.router, prefix=f"{settings.API_V1_STR}/ocr", tags=["ocr"])


@app.get("/")
def root():
    return {"message": f"{settings.PROJECT_NAME} is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
