FROM node:24-bookworm-slim AS build
WORKDIR /srv
COPY package.json package-lock.json ./
RUN npm ci --force
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/dist/sommelier-frontend/browser /usr/share/nginx/html
EXPOSE 80
