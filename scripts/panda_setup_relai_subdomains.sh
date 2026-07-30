#!/usr/bin/env bash
# Install imagemanager.relai.asia + tnexus.relai.asia nginx vhosts and TLS on Panda.
# DNS A records must point to Panda public IP first (Cloudflare proxied=false).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EMAIL="${CERTBOT_EMAIL:-croppedtraveller@gmail.com}"

install_http_only() {
  local dom="$1"
  cat >"/etc/nginx/sites-available/${dom}.conf" <<EOF
server {
    listen 10.3.0.7:80;
    server_name ${dom};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 200 "pending tls for ${dom}\n";
        add_header Content-Type text/plain;
    }
}
EOF
  ln -sf "/etc/nginx/sites-available/${dom}.conf" "/etc/nginx/sites-enabled/${dom}.conf"
}

for dom in imagemanager.relai.asia tnexus.relai.asia; do
  if [[ ! -f "/etc/letsencrypt/live/${dom}/fullchain.pem" ]]; then
    install_http_only "$dom"
  fi
done

nginx -t
systemctl reload nginx

for dom in imagemanager.relai.asia tnexus.relai.asia; do
  if [[ ! -f "/etc/letsencrypt/live/${dom}/fullchain.pem" ]]; then
    certbot certonly --webroot -w /var/www/html -d "$dom" \
      --non-interactive --agree-tos -m "$EMAIL"
  fi
done

cp "$ROOT/deploy/nginx/imagemanager.relai.asia.conf" /etc/nginx/sites-available/imagemanager.relai.asia.conf
cp "$ROOT/deploy/nginx/tnexus.relai.asia.conf" /etc/nginx/sites-available/tnexus.relai.asia.conf
ln -sf /etc/nginx/sites-available/imagemanager.relai.asia.conf /etc/nginx/sites-enabled/imagemanager.relai.asia.conf
ln -sf /etc/nginx/sites-available/tnexus.relai.asia.conf /etc/nginx/sites-enabled/tnexus.relai.asia.conf

nginx -t
systemctl reload nginx

echo "OK: imagemanager.relai.asia + tnexus.relai.asia nginx + TLS"
