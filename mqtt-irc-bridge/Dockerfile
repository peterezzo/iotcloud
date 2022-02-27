FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY mqtt-irc-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-irc-bridge.py" ]
