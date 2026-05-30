FROM python:3.12-slim
WORKDIR /app
COPY app/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/api/ .
COPY data/laurie-engine /data/laurie-engine
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
