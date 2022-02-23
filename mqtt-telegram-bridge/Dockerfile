FROM python:3-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN apk add build-base postgresql-dev && pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY lib/*/*.py mqtt-telegram-bridge/mqtt-telegram-bridge.py ./

USER 1000:1000

CMD [ "python", "./mqtt-telegram-bridge.py" ]
