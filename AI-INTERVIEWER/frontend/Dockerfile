# Next.js frontend for the AI interviewer
# Uses pnpm + pnpm-lock.yaml (the project's package manager) so versions match local dev
FROM node:22-alpine AS base
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM base AS run
ENV NODE_ENV=production \
    PORT=3000
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/next.config.ts ./
USER node
EXPOSE 3000
# LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are read at runtime (--env-file .env.local)
CMD ["node_modules/.bin/next", "start"]
