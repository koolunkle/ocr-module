"""
API 요청 처리를 위한 공통 의존성 정의
"""

import io
from typing import Tuple
from fastapi import UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError
from app.core.constants import ALLOWED_IMAGE_EXTENSIONS


async def validate_image_file(file: UploadFile = File(...)) -> Tuple[Image.Image, str]:
    """업로드 파일 확장자 검증 및 PIL 객체 변환"""
    filename = file.filename or ""
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 확장자입니다. 허용: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    try:
        image = Image.open(io.BytesIO(await file.read()))
        image.load()
        return image, filename
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="유효하지 않은 이미지 파일입니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 처리 오류: {str(e)}")
