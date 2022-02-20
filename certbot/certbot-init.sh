#!/bin/sh

while :
do
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        echo "Existing cert found, renewing"
        certbot renew
    else
        certbot certonly --register-unsafely-without-email --agree-tos \
        --dns-digitalocean --dns-digitalocean-credentials /do-api.ini \
        -d $DOMAIN
    fi
    sleep 24h
done
