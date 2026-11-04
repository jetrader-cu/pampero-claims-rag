# Etapa de construcción
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
COPY node_modules ./node_modules
COPY . .

RUN ./node_modules/.bin/tsc -b && ./node_modules/.bin/vite build

# Etapa de ejecución con Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
