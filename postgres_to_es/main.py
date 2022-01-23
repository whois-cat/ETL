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
from state import State, BaseStorage, JsonFileStorage

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
                             'id', fw.id,
                             'title', fw.title)
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
                            'id', pfw.film_work_id, 
                            'title', fw.title, 
                            'role', pfw.role,
                            'imdb_rating', fw.rating)
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


class Extraction:
    def __init__(self, conn, query) -> None:
        self.cursor = conn.cursor()
        self.query = query

    @backoff.on_exception(
        wait_gen=backoff.expo, exception=(psycopg2.Error, psycopg2.OperationalError)
    )
    def extract(self, since_last_updated):
        self.cursor.execute(self.query["query"], {"date": (since_last_updated,)})
        logging.info("Data extracted.")
        while batch := self.cursor.fetchmany(int(os.environ.get("BATCH_SIZE"))):
            yield from batch


class Transform:
    def __init__(self, conn, query, data) -> None:
        self.query = query
        self.data = data
        self.cursor = conn.cursor()

    def transform(self):
        if self.query["index"] == "movies":
            for f in (
                "actors_names",
                "writers_names",
                "actors",
                "writers",
            ):
                if self.data[f] is None:
                    self.data[f] = []
        return self.query["model"](**data)


class Load:
    def __init__(self, conn, data_obj) -> None:
        self.data_obj = data_obj
        self.cursor = conn.cursor()
        self.es = Elasticsearch([f'{os.environ.get("ES_HOST")}'])

    @backoff.on_exception(
        wait_gen=backoff.expo,
        exception=(ElasticsearchException, HTTPError),
        max_tries=10,
    )
    def load_data(self) -> None:
        self.es.index(
            index=query["index"],
            doc_type="doc",
            id=self.data_obj.id,
            body=self.data_obj.dict(),
        )
        logging.info("Data loaded.")


if __name__ == "__main__":
    dsn = {
        "dbname": os.environ.get("POSTGRES_DB"),
        "user": os.environ.get("POSTGRES_USER"),
        "password": os.environ.get("POSTGRES_PASSWORD"),
        "host": os.environ.get("POSTGRES_HOST"),
        "port": os.environ.get("POSTGRES_PORT"),
    }
    state = State(storage=JsonFileStorage(file_path="state.json"))
    with closing(psycopg2.connect(**dsn, cursor_factory=RealDictCursor)) as pg_conn:
        logging.info("PostgreSQL connection is open. Start load movies data.")
        while True:
            for query in queries:
                state_key = f"last_{query['index']}_updated_at"
                since = datetime.fromisoformat(state.get_state(state_key) or '1970-01-01T00:00:00')
                for data in Extraction(pg_conn, query).extract(since_last_updated=since):
                    data_obj = Transform(pg_conn, query, data).transform()
                    Load(pg_conn, data_obj).load_data()
                    state.set_state(
                        state_key,
                        data["all_updated_at"].isoformat(),
                    )
            sleep(1)
