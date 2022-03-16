FROM python:3-alpine

COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN apk add --update --no-cache chrony tzdata && \
    cp /usr/share/zoneinfo/UTC /etc/localtime && \
    echo UTC > /etc/timezone

HEALTHCHECK CMD chronyc tracking || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]

CMD ["-u", "chrony", "-d", "-x", "-L", "0"]
