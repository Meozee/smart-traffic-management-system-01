FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY . /layer2_backend
RUN pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose passlib bcrypt python-multipart opencv-python-headless ultralytics
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "layer2_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]