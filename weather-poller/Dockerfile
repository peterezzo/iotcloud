FROM ghcr.io/peterezzo/iotcloud_base:latest

COPY weather-poller.py ./

USER 1000:1000

CMD [ "python", "./weather-poller.py" ]
