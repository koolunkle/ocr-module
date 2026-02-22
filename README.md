# RapidOCR API Service

A high-performance OCR REST API based on **FastAPI** and **RapidOCR**, designed for processing document images and extracting structured data.

## Features

- **High-Performance OCR**: Powered by RapidOCR (ONNX Runtime) for fast and accurate text recognition.
- **Parallel Processing**: Supports multi-threaded processing for multi-page documents (e.g., TIFF).
- **Streaming Support**: Real-time results via Server-Sent Events (SSE).
- **Structured Parsing**: Automatically classifies and extracts key-value pairs from documents.
- **Modern Tooling**: Managed with **uv** for blazing-fast dependency management.

## Tech Stack

- **Framework**: FastAPI
- **OCR Engine**: RapidOCR (PaddleOCR-based)
- **Runtime**: ONNX Runtime
- **Environment**: Python 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

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
Ensure your ONNX models and dictionary files are placed in the `models/` directory.

### 3. Environment Setup
Create a `.env` file from the template and configure your settings:
```bash
# Example .env configuration
PROJECT_NAME="RapidOCR API Service"
USE_CLS=false
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
- **Description**: Processes an entire image or specific pages and returns results in a single response.

### Streaming Processing
- **URL**: `POST /api/v1/ocr/stream`
- **Description**: Streams OCR results page-by-page using Server-Sent Events (SSE).

---
*Note: This project is designed for general-purpose document analysis and can be extended for various domain-specific needs.*
