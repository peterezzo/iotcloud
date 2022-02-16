FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY lib/*/*.py mqtt-postgres-bridge/mqtt-postgres-bridge.py ./

CMD [ "python", "./mqtt-postgres-bridge.py" ]
