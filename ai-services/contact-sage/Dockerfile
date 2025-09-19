FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir --timeout=100 --retries=5 -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8083"]
