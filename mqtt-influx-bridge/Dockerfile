FROM iotcloud_base

COPY mqtt-influx-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-influx-bridge.py" ]

HEALTHCHECK CMD [ "test", "-n", "$(find /dev/shm/healthcheck -mmin -5)" ]
