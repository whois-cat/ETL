import os
import json
import psycopg2
import logging
import backoff
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime
from models import FilmWork
from contextlib import closing
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException
from urllib3.exceptions import HTTPError
from state import State, JsonFileStorage
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
load_dotenv()


class ETL:
    def __init__(self, conn):
        self.cursor = conn.cursor()
        self.state = State(storage=JsonFileStorage(file_path="state.json"))
        self.es = Elasticsearch([f'{os.environ.get("ES_HOST")}'])

    def get_state(self):
        last_last_updated_at = self.state.get_state("last_last_updated_at")
        if last_last_updated_at is None:
            last_last_updated_at = datetime.fromtimestamp(0)
        else:
            last_last_updated_at = datetime.fromisoformat(last_last_updated_at)
        return last_last_updated_at

    @backoff.on_exception(
        wait_gen=backoff.expo, exception=(psycopg2.Error, psycopg2.OperationalError)
    )
    def get_and_load_data(self):
        query: str = """
            SELECT
                fw.id,
                fw.title,
                fw.type,
                fw.description,
                fw.rating as imdb_rating,
                fw.created_at, 
                fw.updated_at, 
                ARRAY_AGG(DISTINCT g.name) AS genre,
                ARRAY_AGG(DISTINCT p.full_name) FILTER (WHERE pfw.role = 'actor') AS actors_names, 
                ARRAY_AGG(DISTINCT p.full_name) FILTER (WHERE pfw.role = 'writer') AS writers_names,
                STRING_AGG(DISTINCT p.full_name, ',') FILTER (WHERE pfw.role = 'director') as director,
                JSON_AGG(DISTINCT jsonb_build_object('id', p.id, 'name', p.full_name)) FILTER (WHERE pfw.role = 'actor') AS actors,
                JSON_AGG(DISTINCT jsonb_build_object('id', p.id, 'name', p.full_name)) FILTER (WHERE pfw.role = 'writer') AS writers
            FROM content.film_work fw
            LEFT OUTER JOIN content.genre_film_work gfw ON fw.id = gfw.film_work_id
            LEFT OUTER JOIN content.genre g ON (gfw.genre_id = g.id)
            LEFT OUTER JOIN content.person_film_work pfw ON (fw.id = pfw.film_work_id)
            LEFT OUTER JOIN content.person p ON (pfw.person_id = p.id)
            WHERE fw.updated_at > %s
            GROUP BY fw.id, fw.title, fw.description, fw.rating
            ORDER BY fw.updated_at;
        """
        self.cursor.execute(query, (self.get_state(),))
        logging.info("Data extracted.")
        while batch := self.cursor.fetchmany(int(os.environ.get("BATCH_SIZE"))):
            yield from batch

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(ElasticsearchException, HTTPError),
        max_tries=10,
    )
    def load_data(self):
        for data in self.get_and_load_data():
            for f in (
                "actors_names",
                "writers_names",
                "actors",
                "writers",
            ):
                if data[f] is None:
                    data[f] = []
            data_obj = FilmWork(**data)
            self.es.index(
                index="movies", doc_type="doc", id=data_obj.id, body=data_obj.dict()
            )
            self.state.set_state("last_last_updated_at", data["updated_at"].isoformat())
        logging.info("Data loaded.")


if __name__ == "__main__":
    dsn = {
        "dbname": os.environ.get("POSTGRES_DB"),
        "user": os.environ.get("POSTGRES_USER"),
        "password": os.environ.get("POSTGRES_PASSWORD"),
        "host": os.environ.get("POSTGRES_HOST"),
        "port": os.environ.get("POSTGRES_PORT"),
    }
    with closing(psycopg2.connect(**dsn, cursor_factory=RealDictCursor)) as pg_conn:
        logging.info("PostgreSQL connection is open. Start load movies data.")
        ETL(pg_conn).load_data()
