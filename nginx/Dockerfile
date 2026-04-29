FROM nginx:1.27-alpine

# Generate self-signed cert at build time for dev (overridden by mounted volume in prod)
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/certs \
    && openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/certs/dev.key \
        -out /etc/nginx/certs/dev.crt \
        -subj "/C=ID/ST=Dev/L=Local/O=ROC/CN=localhost" \
    && apk del openssl

COPY nginx.conf /etc/nginx/nginx.conf
COPY proxy_params.conf /etc/nginx/proxy_params.conf

EXPOSE 80 443
