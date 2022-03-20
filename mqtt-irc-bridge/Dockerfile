FROM iotcloud_base

COPY mqtt-irc-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-irc-bridge.py" ]

HEALTHCHECK CMD [ "test", "-n", "$(find /dev/shm/healthcheck -mmin -1)" ]
