FROM node:22-alpine AS frontend-source
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend .

FROM frontend-source AS test
RUN npm test

FROM frontend-source AS build
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
