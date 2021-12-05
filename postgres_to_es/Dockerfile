FROM python:3.9-slim

WORKDIR /etl

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

COPY requirements.txt /etl/

RUN pip install --upgrade pip \
    && pip install -r requirements.txt
COPY . /etl/