# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.28.0 --activate
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY . .
ARG VITE_TRACE_URL_TEMPLATE
ENV VITE_TRACE_URL_TEMPLATE=${VITE_TRACE_URL_TEMPLATE}
# Tipos y bundle se generan dentro de la imagen; en el host solo se ejecutan lint, tipos y tests.
RUN pnpm exec tsc -b && pnpm exec vite build

FROM nginx:1.29-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
