import logging
import os
import sys
from contextlib import closing
from datetime import datetime
from inspect import cleandoc
from time import sleep

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from urllib3.exceptions import HTTPError

import backoff
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException
from models import FilmWork, Genre, Person
from state import JsonFileStorage, State

logging.basicConfig(level=logging.INFO)
load_dotenv()

queries = (
    {
        "index": "movies",
        "model": FilmWork,
        "query": cleandoc(
            """
                    SELECT
                        fw.id,
                        fw.title,
                        fw.type,
                        fw.description,
                        fw.rating as imdb_rating,
                        fw.created_at,
                        fw.updated_at,
                    JSON_AGG(DISTINCT jsonb_build_object('id', g.id, 'name', g.name)) AS genre,
                    ARRAY_AGG(DISTINCT p.full_name) FILTER (WHERE pfw.role = 'actor') AS actors_names,
                    ARRAY_AGG(DISTINCT p.full_name) FILTER (WHERE pfw.role = 'writer') AS writers_names,
                    GREATEST(
                        fw.updated_at,
                        MAX(g.updated_at),
                        MAX(DISTINCT p.updated_at) FILTER (WHERE pfw.role = 'writer'),
                        MAX(DISTINCT p.updated_at) FILTER (WHERE pfw.role = 'actor'),
                        MAX(DISTINCT p.updated_at) FILTER (WHERE pfw.role = 'director')
                    ) as all_updated_at,
                    JSON_AGG(DISTINCT jsonb_build_object('id', p.id, 'name', p.full_name)) FILTER (WHERE pfw.role = 'director') -> 0 AS director,
                    JSON_AGG(DISTINCT jsonb_build_object('id', p.id, 'name', p.full_name)) FILTER (WHERE pfw.role = 'actor') AS actors,
                    JSON_AGG(DISTINCT jsonb_build_object('id', p.id, 'name', p.full_name)) FILTER (WHERE pfw.role = 'writer') AS writers
                    FROM content.film_work fw
                    LEFT OUTER JOIN content.genre_film_work gfw ON fw.id = gfw.film_work_id
                    LEFT OUTER JOIN content.genre g ON (gfw.genre_id = g.id)
                    LEFT OUTER JOIN content.person_film_work pfw ON (fw.id = pfw.film_work_id)
                    LEFT OUTER JOIN content.person p ON (pfw.person_id = p.id)
                    GROUP BY fw.id, fw.title, fw.description, fw.rating
                    HAVING fw.updated_at > %(date)s OR MAX(g.updated_at) > %(date)s OR MAX(p.updated_at) > %(date)s
                    ORDER BY fw.updated_at;
                """
        ),
    },
    {
        "index": "genres",
        "model": Genre,
        "query": cleandoc(
            """
                     SELECT
                         g.id,
                         g.name,
                         g.created_at,
                         g.updated_at,
                         GREATEST(
                             g.updated_at,
                             MAX(gfw.created_at),
                             MAX(fw.updated_at)
                         ) as all_updated_at,
                         JSON_AGG(DISTINCT jsonb_build_object(
                             'title', fw.title, 
                             'id', gfw.id, 
                             'film_work_id', gfw.film_work_id)
                         ) AS films
                     FROM content.genre g
                     LEFT OUTER JOIN content.genre_film_work gfw ON (g.id = gfw.genre_id)
                     LEFT OUTER JOIN content.film_work fw ON (gfw.film_work_id = fw.id)
                     GROUP BY g.id, g.name
                     HAVING g.updated_at > %(date)s OR MAX(gfw.created_at) > %(date)s or MAX(fw.updated_at) > %(date)s
                     ORDER BY g.updated_at;
                """
        ),
    },
    {
        "index": "persons",
        "model": Person,
        "query": cleandoc(
            """
                    SELECT
                        p.id,
                        p.full_name,
                        p.created_at,
                        p.updated_at,
                        GREATEST(
                            p.updated_at,
                            MAX(pfw.created_at),
                            MAX(fw.updated_at)
                        ) AS all_updated_at,
                        JSON_AGG(DISTINCT jsonb_build_object(
                            'title', fw.title, 
                            'id', pfw.id, 
                            'film_work_id', pfw.film_work_id, 
                            'role', pfw.role)
                        ) AS films
                    FROM content.person p
                    LEFT OUTER JOIN content.person_film_work pfw ON (p.id = pfw.person_id)
                    LEFT OUTER JOIN content.film_work fw ON (pfw.film_work_id = fw.id)
                    GROUP BY p.id, p.full_name
                    HAVING p.updated_at > %(date)s OR MAX(pfw.created_at) > %(date)s or MAX(fw.updated_at) > %(date)s
                    ORDER BY p.updated_at;
                """
        ),
    },
)


class ETL:
    def __init__(self, conn) -> None:
        self.cursor = conn.cursor()
        self.state = State(storage=JsonFileStorage(file_path="state.json"))
        self.es = Elasticsearch([f'{os.environ.get("ES_HOST")}'])

    def get_state(self, index) -> datetime:
        last_last_updated_at = self.state.get_state(f"last_{index}_updated_at")
        if last_last_updated_at is None:
            last_last_updated_at = datetime.fromtimestamp(0)
        else:
            last_last_updated_at = datetime.fromisoformat(last_last_updated_at)
        return last_last_updated_at

    @backoff.on_exception(
        wait_gen=backoff.expo, exception=(psycopg2.Error, psycopg2.OperationalError)
    )
    def extract(self, query):
        self.cursor.execute(query["query"], {"date": (self.get_state(query["index"]),)})
        logging.info("Data extracted.")
        while batch := self.cursor.fetchmany(int(os.environ.get("BATCH_SIZE"))):
            yield from batch

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(ElasticsearchException, HTTPError),
        max_tries=10,
    )
    def load_data(self) -> None:
        for query in queries:
            for data in self.extract(query):
                if query["index"] == "movies":
                    for f in (
                        "actors_names",
                        "writers_names",
                        "actors",
                        "writers",
                    ):
                        if data[f] is None:
                            data[f] = []
                data_obj = query["model"](**data)
                self.es.index(
                    index=query["index"],
                    doc_type="doc",
                    id=data_obj.id,
                    body=data_obj.dict(),
                )
                self.state.set_state(
                    f"last_{query['index']}_updated_at",
                    data["all_updated_at"].isoformat(),
                )
            logging.info("Data loaded.")

    def etl(self) -> None:
        while True:
            self.load_data()
            sleep(1)


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
        ETL(pg_conn).etl()
