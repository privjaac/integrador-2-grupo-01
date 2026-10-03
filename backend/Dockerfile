FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --system app && useradd --system --gid app app
COPY --chown=app:app . .
USER app

# Render supplies PORT at runtime. Migration failures stop startup.
CMD ["sh", "-ec", ": \"${PORT:?PORT must be set}\"; python manage.py migrate --noinput; exec uvicorn api.main:app --host 0.0.0.0 --port \"$PORT\""]
