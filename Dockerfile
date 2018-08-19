FROM python:2.7-stretch

WORKDIR /app

RUN apt-get update && \
    apt-get -y install python-requests python-smbc python-lxml python-dnspython

COPY docker/requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD python run.py
