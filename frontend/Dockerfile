# Multi-stage build for a small Next.js production image.

# --- Stage 1: install deps ------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# --- Stage 2: build -------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

# NEXT_PUBLIC_* vars must be baked at build time — they're inlined into the JS
# bundle. Compose passes these via build args.
ARG NEXT_PUBLIC_ORACLE_HTTP=http://localhost:8000
ARG NEXT_PUBLIC_ORACLE_WS=ws://localhost:8000/ws
ENV NEXT_PUBLIC_ORACLE_HTTP=$NEXT_PUBLIC_ORACLE_HTTP
ENV NEXT_PUBLIC_ORACLE_WS=$NEXT_PUBLIC_ORACLE_WS

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Stage 3: runtime -----------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy only what's needed to run.
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./

EXPOSE 3000
CMD ["npm", "run", "start"]
