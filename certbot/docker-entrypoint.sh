#!/bin/sh

echo $DIGITALOCEAN_API_TOKEN > /do-api.ini

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
    chmod -R g+rX,o+rX /etc/letsencrypt/*
    sleep 24h
done
