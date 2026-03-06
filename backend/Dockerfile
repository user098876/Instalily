FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY workers ./workers
COPY scripts ./scripts
ENV PYTHONPATH=/app/backend:/app/workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
