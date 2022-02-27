FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY syslog-influx-bridge.py ./

USER 1000:1000

CMD [ "python", "./syslog-influx-bridge.py" ]
