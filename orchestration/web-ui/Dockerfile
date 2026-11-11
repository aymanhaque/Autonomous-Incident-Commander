FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
# Ship nginx.conf as a *.template so the base image's docker-entrypoint envsubst
# step (20-envsubst-on-templates.sh) renders it to /etc/nginx/conf.d/default.conf
# at container start, injecting ${APPROVAL_API_TOKEN} into the /approvals/ proxy
# Authorization header. NGINX_ENVSUBST_FILTER restricts substitution to that one
# variable so nginx runtime vars ($host, $uri, $remote_addr, ...) are preserved.
ENV NGINX_ENVSUBST_FILTER=APPROVAL_API_TOKEN
COPY nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
