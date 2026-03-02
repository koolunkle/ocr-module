"""
[API] 공통 의존성 및 데이터 검증
역할: 이미지 업로드 파일의 확장자 유효성을 검사하고 PIL 객체로 변환합니다.
"""

import io
from typing import Tuple

from fastapi import File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.constants import ALLOWED_IMAGE_EXTS


async def validate_image_file(file: UploadFile = File(...)) -> Tuple[Image.Image, str]:
    """
    업로드된 파일이 유효한 이미지인지 검사하고 파일명과 함께 반환
    - 지원 형식: PNG, JPG, JPEG, TIF, TIFF, BMP 등
    """
    filename = file.filename or "unknown"
    # 파일 확장자 추출 및 소문자 통일
    ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    # 허용되지 않은 확장자인 경우 400 에러 반환
    if ext not in ALLOWED_IMAGE_EXTS:
        allowed_list = ", ".join(ALLOWED_IMAGE_EXTS)
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. (허용: {allowed_list})",
        )

    try:
        # 업로드된 바이너리 데이터를 PIL 이미지로 변환
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        # 이미지 데이터가 메모리에 실제로 로드되었는지 확인
        image.load()
        return image, filename

    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="이미지 파일을 읽을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 전처리 도중 예상치 못한 오류가 발생했습니다: {str(e)}")
