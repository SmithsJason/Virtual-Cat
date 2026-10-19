FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-deps .
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
COPY alembic.ini ./
COPY alembic ./alembic
RUN useradd --create-home companion
# Keep tokenizer cache accessible to the unprivileged runtime user.
RUN chmod -R a+rX /tmp/data-gym-cache || true
USER companion
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
