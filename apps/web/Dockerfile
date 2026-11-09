FROM node:22-alpine AS build
WORKDIR /web
COPY apps/web/package*.json apps/web/.npmrc ./
RUN npm ci
COPY apps/web/ .
RUN npm run build

FROM nginx:stable-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
