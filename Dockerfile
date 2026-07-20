FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 hermes \
    && mkdir -p /app/data \
    && chown -R hermes:hermes /app
USER hermes

EXPOSE 8080
CMD ["hermes-a2a", "serve"]
