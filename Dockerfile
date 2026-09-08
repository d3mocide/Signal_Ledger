FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
COPY --from=frontend /frontend/dist/ ./app/static/
COPY supervisord.conf ./
RUN useradd --system --create-home ledger && mkdir -p /var/lib/signal-ledger/raw && chown -R ledger:ledger /app /var/lib/signal-ledger
USER ledger
EXPOSE 8000
CMD ["supervisord", "-c", "/app/supervisord.conf"]
