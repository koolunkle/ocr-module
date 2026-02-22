import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app

# FastAPI 테스트 클라이언트 초기화
client = TestClient(app)


def create_dummy_image(extension="png"):
    """테스트를 위한 임시 이미지 생성"""
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="white")
    image.save(file, format=extension.upper())
    file.seek(0)
    return file


def test_read_root():
    """서버 기동 확인 테스트"""
    response = client.get("/")
    assert response.status_code == 200
    assert "RapidOCR API Service" in response.json()["message"]


def test_ocr_invalid_file_type():
    """허용되지 않는 파일 확장자 테스트"""
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = client.post("/api/v1/ocr/", files=files)
    assert response.status_code == 400
    assert "지원하지 않는 확장자" in response.json()["detail"]


def test_ocr_process_success():
    """일반 OCR 처리 성공 테스트"""
    img_file = create_dummy_image("png")
    files = {"file": ("test.png", img_file, "image/png")}

    response = client.post("/api/v1/ocr/", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "filename" in data
    assert "pages" in data
    assert isinstance(data["pages"], list)


def test_ocr_process_with_pages():
    """특정 페이지 지정 테스트"""
    img_file = create_dummy_image("png")
    files = {"file": ("test.png", img_file, "image/png")}
    data = {"pages": "1"}

    response = client.post("/api/v1/ocr/", files=files, data=data)
    assert response.status_code == 200
    assert len(response.json()["pages"]) == 1


def test_ocr_stream_success():
    """스트리밍 OCR 처리 성공 테스트"""
    img_file = create_dummy_image("png")
    files = {"file": ("test.png", img_file, "image/png")}

    # stream=True를 사용하여 응답을 순차적으로 받음
    with client.stream("POST", "/api/v1/ocr/stream", files=files) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # 첫 번째 데이터 라인 확인
        for line in response.iter_lines():
            if line.startswith("data: "):
                assert "page_num" in line
                break
