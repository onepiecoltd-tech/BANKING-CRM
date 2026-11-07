# Backend FastAPI cho VPS. Build từ thư mục gốc dự án:  docker compose -f deploy/docker-compose.yml build
FROM python:3.11-slim

# Tesseract để OCR PDF scan/ảnh (Việt, Anh, Trung giản thể)
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng tesseract-ocr-chi-sim curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

ENV CRM_ENV=production \
    DATABASE_URL=sqlite:////data/banking_crm.db \
    CRM_BACKUP_DIR=/data/backups \
    PYTHONUNBUFFERED=1
VOLUME /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# --proxy-headers: lấy IP thật của người dùng từ Caddy (cổng 8000 không mở ra ngoài, chỉ Caddy gọi được)
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
