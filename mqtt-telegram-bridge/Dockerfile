FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY mqtt-telegram-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-telegram-bridge.py" ]
