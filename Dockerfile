FROM python:2.7.13-alpine

ADD check-reserved-instances.py /check-reserved-instances.py
ADD bootstrap.sh /bootstrap.sh
ADD requirements.txt /requirements.txt

WORKDIR /

RUN apk --update --no-cache add curl jq && pip install -r requirements.txt

CMD ./bootstrap.sh
