FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY syslog-influxdb-bridge.py ./

CMD [ "python", "./syslog-influxdb-bridge.py" ]
