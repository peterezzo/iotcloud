FROM iotcloud_base

COPY mqtt-postgres-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-postgres-bridge.py" ]

HEALTHCHECK CMD test -n "$(find /dev/shm/healthcheck -mmin -1 2>/dev/null)"
