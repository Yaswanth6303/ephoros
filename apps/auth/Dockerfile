# Build context: repository root. Node 24 runs the TypeScript sources directly (type stripping).
FROM node:24.22.0-slim
RUN npm install -g pnpm@12.14.0
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# shortcut: prod install pulls the whole root dependency set, split with `pnpm deploy` if image size matters
# npm is only needed to install pnpm; removing it drops its bundled packages (and their CVEs) from the runtime image
RUN pnpm install --frozen-lockfile --prod && npm uninstall -g pnpm \
  && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx
COPY apps/auth/package.json apps/auth/package.json
COPY apps/auth/src apps/auth/src
ENV NODE_ENV=production PORT=3000
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD ["node", "-e", "fetch('http://localhost:3000/api/auth/ok').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
CMD ["node", "apps/auth/src/main.ts"]
