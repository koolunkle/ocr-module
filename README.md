# RapidOCR API Service

A high-performance OCR REST API based on **FastAPI** and **RapidOCR**, designed for processing document images and extracting structured data, specifically optimized for legal and judicial documents.

## Features

- **High-Performance OCR**: Powered by RapidOCR (ONNX Runtime) for fast and accurate text recognition.
- **Parallel Processing**: Supports multi-threaded processing for multi-page documents (e.g., TIFF, multi-page PDFs).
- **Streaming Support**: Real-time results via Server-Sent Events (SSE) for large documents.
- **Structured Parsing**: Automatically extracts key-value pairs such as Case Number, Court Name, Creditor/Debtor information, and Claim Amounts.
- **Modern Tooling**: Managed with **uv** for blazing-fast dependency management.

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (>=0.128.0)
- **OCR Engine**: [RapidOCR](https://github.com/RapidAI/RapidOCR) (>=3.5.0)
- **Layout Analysis**: [Rapid-Layout](https://github.com/RapidAI/RapidLayout) (>=1.2.0)
- **Runtime**: ONNX Runtime (>=1.23.2)
- **Environment**: Python 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

## Project Structure

```text
OCR_RapidOCR_Module/
├── app/
│   ├── api/          # API layer (FastAPI endpoints and dependencies)
│   ├── engine/       # Core OCR logic (layout, parser, processor, utils)
│   ├── config.py     # Configuration management
│   ├── constants.py  # Shared constants
│   ├── main.py       # Application entry point
│   └── schemas.py    # Pydantic models for request/response validation
├── models/           # ONNX models and dictionary files
├── tests/            # Test suite
├── pyproject.toml    # Dependency and project configuration
└── uv.lock           # Dependency lock file
```

## Getting Started

### 1. Installation
We recommend using **uv** for faster setup:
```bash
# Using uv (Recommended)
uv sync

# Using pip
pip install -r requirements.txt
```

### 2. Model Preparation
Ensure your ONNX models (detection, recognition, classifier, layout) and dictionary files are placed in the `models/` directory.

### 3. Environment Setup
Create a `.env` file and configure your settings:
```bash
# Example .env configuration
PROJECT_NAME="RapidOCR API Service"
USE_CLS=false
DEBUG=true
OCR_MAX_WORKERS=4
```

### 4. Run Server
```bash
# Using uv
uv run python -m app.main

# Using standard python
python -m app.main
```

## API Endpoints

### Batch Processing
- **URL**: `POST /api/v1/ocr/`
- **Parameters (Form Data)**:
  - `file`: The image or document file to process.
  - `pages` (Optional): Specific page numbers to process (e.g., `"1,3,5"`).
- **Description**: Processes the document and returns all results in a single JSON response.

### Streaming Processing
- **URL**: `POST /api/v1/ocr/stream`
- **Parameters (Form Data)**:
  - `file`: The image or document file to process.
  - `pages` (Optional): Specific page numbers to process (e.g., `"1,3,5"`).
- **Description**: Streams OCR results page-by-page using Server-Sent Events (SSE).

---
*Note: This project includes specialized parsing logic for Korean legal documents but can be extended for other domain-specific needs.*
