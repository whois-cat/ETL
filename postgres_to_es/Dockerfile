FROM python:3.9

WORKDIR /etl

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

COPY requirements.txt /etl/

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

ENTRYPOINT ["sh", "-c", "sleep 10 && sh /etl/schema.sh || true &&  python3 main.py"]
