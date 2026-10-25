# Build context: repository root.
FROM node:24.22.0-slim AS build
RUN npm install -g pnpm@12.14.0
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY nx.json tsconfig.base.json ./
COPY apps/web apps/web
COPY libs libs
RUN NX_DAEMON=false NX_NO_CLOUD=true pnpm nx build web

FROM nginxinc/nginx-unprivileged:stable-alpine
# apply Alpine security fixes released after the base image was built, then drop back to its nginx user
USER root
RUN apk upgrade --no-cache
USER 101
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/apps/web/browser /usr/share/nginx/html
EXPOSE 8080
