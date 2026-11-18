FROM node:22.23.4-bookworm-slim AS web-build
WORKDIR /build/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
# Only the internal API address is needed at build time. No database/model secrets.
ENV API_ORIGIN=http://127.0.0.1:8000
RUN npm run build

FROM python:3.14.10-slim-bookworm AS api-build
WORKDIR /build
COPY apps/api/requirements.lock ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r requirements.lock

FROM python:3.14.10-slim-bookworm AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libstdc++6 libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 funilo \
    && useradd --uid 10001 --gid funilo --create-home funilo
COPY --from=web-build /usr/local/bin/node /usr/local/bin/node
COPY --from=api-build /opt/venv /opt/venv
WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/apps/api \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    APP_ENV=production \
    APP_ORIGIN=https://moodigo.ir \
    DATA_BACKEND=mongo \
    API_WORKERS=1 \
    WEB_CONCURRENCY=1 \
    JOB_RUNNER_MODE=in_process \
    LLM_PROVIDER=demo \
    DEMO_CONTENT=true \
    PORT=3000
COPY --chown=funilo:funilo apps/api/app/ ./apps/api/app/
COPY --chown=funilo:funilo DRAMMA_450_activities_fa.json ./
COPY --chown=funilo:funilo content/cooked-examples.md content/demo-extra.json content/demo-catalog.json content/demo-cook-fixtures.json ./content/
COPY --chown=funilo:funilo content/activities.json content/iran-catalog.json content/dramma-legacy-checksums.json content/short-now.txt content/long-now.txt ./content/
COPY --chown=funilo:funilo content/practical-now.txt ./content/
COPY --chown=funilo:funilo content/northern-outings.txt ./content/
COPY --chown=funilo:funilo scripts/container.py ./scripts/container.py
COPY --from=web-build --chown=funilo:funilo /build/web/.next/standalone/ ./apps/web/
COPY --from=web-build --chown=funilo:funilo /build/web/.next/static/ ./apps/web/.next/static/
COPY --from=web-build --chown=funilo:funilo /build/web/public/ ./apps/web/public/
USER funilo
EXPOSE 3000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "/app/scripts/container.py", "--healthcheck"]
CMD ["python", "/app/scripts/container.py"]
