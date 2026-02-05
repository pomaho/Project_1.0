FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json /app/package.json
ENV npm_config_platform=linux
ENV npm_config_arch=x64
ENV npm_config_libc=musl
RUN npm config set registry https://registry.npmjs.org/ \
    && npm config set fund false \
    && npm config set audit false
RUN npm install --loglevel=info
COPY frontend /app
RUN npm run build

FROM nginx:1.25-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
