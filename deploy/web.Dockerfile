# Giao diện: build bản tĩnh (SPA) rồi để Caddy phục vụ + proxy /api sang backend + HTTPS tự động.
FROM node:22-slim AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN STATIC_SPA=1 npm run build

FROM caddy:2-alpine
COPY --from=build /src/dist/client /srv
# _shell.html là trang khởi động của SPA; thêm bản index.html để đường dẫn gốc "/" luôn hoạt động
RUN cp /srv/_shell.html /srv/index.html
COPY deploy/Caddyfile /etc/caddy/Caddyfile
