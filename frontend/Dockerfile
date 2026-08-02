FROM node:24.18.0-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src

RUN npm run build

FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 agentpod \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/agentpod agentpod

COPY --from=build --chown=10001:10001 /build/dist ./dist
COPY --chown=10001:10001 frontend/server.py ./server.py

USER 10001:10001

CMD ["python", "server.py"]
