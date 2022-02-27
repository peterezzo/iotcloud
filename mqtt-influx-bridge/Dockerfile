FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY mqtt-influx-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-influx-bridge.py" ]
