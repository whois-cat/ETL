FROM python:3.9
WORKDIR /home/movies

RUN apt-get update \
    && apt-get -y install postgresql-client

COPY ./movies_admin/requirements.txt /home/movies/
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./movies_admin/ /home/movies

EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "config.wsgi", "app:movies"]
