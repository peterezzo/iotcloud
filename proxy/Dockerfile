FROM python:3-alpine

RUN adduser -u 1000 -D ssh && apk add --no-cache openssh

COPY docker-entrypoint.sh /

USER 1000

ENTRYPOINT [ "/docker-entrypoint.sh" ]
