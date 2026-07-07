FROM python:3.11-slim

WORKDIR /app

# 系统依赖（Pillow 编译需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_web.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 创建临时目录
RUN mkdir -p /tmp/img_converter_uploads

EXPOSE 8000

CMD ["sh", "-c", "uvicorn web_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
