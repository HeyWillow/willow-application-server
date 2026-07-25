ARG WAS_UI_TAG="main"

FROM ghcr.io/heywillow/willow-application-server-ui:${WAS_UI_TAG} AS was-ui

FROM alpine:3.21 AS build

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apk apk add --cache-dir /var/cache/apk alpine-sdk libpq-dev python3-dev uv

COPY pyproject.toml uv.lock ./

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project

COPY . .

COPY --from=was-ui /was-ui/out/ /app/static/admin/

ENV PATH="/opt/venv/bin:$PATH"

RUN PYTHONPATH=/app pytest -s

FROM alpine:3.21

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apk apk add --cache-dir /var/cache/apk libmagic libpq python3

COPY --from=build /app /app
COPY --from=build /opt/venv /opt/venv

EXPOSE 8501
EXPOSE 8502

ARG WAS_VERSION
ENV WAS_VERSION=$WAS_VERSION

CMD /app/entrypoint.sh
