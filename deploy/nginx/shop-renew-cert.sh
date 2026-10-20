#!/bin/sh
# Certbot deploy hook: act only on the shop certificate, never modify DLC files.
set -eu
if [ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/shop.pinlite.dev" ]; then
    /usr/sbin/nginx -t
    /bin/systemctl reload nginx
fi
