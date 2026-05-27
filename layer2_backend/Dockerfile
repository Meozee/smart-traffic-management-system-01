FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app/stms
RUN touch /app/stms/__init__.py
RUN touch /app/stms/routers/__init__.py
WORKDIR /app
CMD ["uvicorn", "stms.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]