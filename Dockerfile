FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY workers ./workers
ENV PYTHONPATH=/app/backend:/app/workers
CMD ["celery", "-A", "workers.tasks", "worker", "--loglevel=INFO"]
