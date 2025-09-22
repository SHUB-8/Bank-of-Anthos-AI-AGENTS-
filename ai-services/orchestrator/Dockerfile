FROM python:3.11-slim
WORKDIR /app
COPY . .

# Set environment variables for production (can be overridden by Kubernetes)
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

# Copy public key if used for JWT validation
COPY public_key.pem ./

RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache /root/.pip

# Optional: set non-root user for security
RUN useradd --create-home appuser
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]