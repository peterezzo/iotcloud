FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY mqtt-postgres-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-postgres-bridge.py" ]
