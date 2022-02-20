FROM docker.io/certbot/dns-digitalocean

COPY certbot/do-api.ini /do-api.ini
COPY certbot/certbot-init.sh /certbot-init.sh

ENTRYPOINT ["/certbot-init.sh"]