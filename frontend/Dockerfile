# 前端镜像：node 构建 → nginx 提供静态 + 反代 /api /webhook /minio
FROM node:22-alpine AS build
WORKDIR /app
# 经宿主 nginx /ticket-api/ 代理到后端 → axios base = /ticket-api/api/v1
ARG VITE_API_BASE=/ticket-api/api/v1
ENV VITE_API_BASE=$VITE_API_BASE
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html/fpy
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
