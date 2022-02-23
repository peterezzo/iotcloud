FROM python:3-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN apk add build-base postgresql-dev && pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY lib/*/*.py mqtt-irc-bridge/mqtt-irc-bridge.py ./

CMD [ "python", "./mqtt-irc-bridge.py" ]
