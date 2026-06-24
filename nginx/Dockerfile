# --- Stage 1: Build frontend ---
FROM node:25-alpine AS build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Serve with nginx ---
FROM nginx:alpine

# Copy built static assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html
# Copy nginx config (can still be overridden by volume mount in compose)
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
