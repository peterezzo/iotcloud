FROM docker.io/certbot/dns-digitalocean

COPY certbot/do-api.ini /do-api.ini
COPY certbot/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]