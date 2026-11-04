# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS builder
WORKDIR /app
RUN npm install -g pnpm@10.28.0 && \
    pnpm config set fetch-retries 5 && \
    pnpm config set fetch-timeout 300000 && \
    pnpm config set network-concurrency 2
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
RUN mkdir -p /usr/share/nginx/html/assets/pdfjs-dist/build && \
    cp /usr/share/nginx/html/assets/pdf.worker.min-*.mjs /usr/share/nginx/html/assets/pdfjs-dist/build/pdf.worker.min.mjs && \
    cp /usr/share/nginx/html/assets/pdf.worker.min-*.mjs /usr/share/nginx/html/pdf.worker.min.mjs
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
