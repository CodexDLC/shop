FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.8
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group web
COPY src/web /app/src/web
COPY src/codex_ecommerce /app/src/codex_ecommerce
COPY manage.py ./
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src" PYTHONUNBUFFERED=1
CMD ["gunicorn", "web.config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
