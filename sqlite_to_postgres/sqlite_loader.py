import logging
import sqlite3
from dataclasses import asdict

from db_classes import FilmWork, Genre, GenreFilmWork, Person, PersonFilmWork


class SQLiteLoader:
    def __init__(self, sqlite_cursor):
        self.cursor = sqlite_cursor

    def load_movies(self):
        def get_data(table):

            try:
                rows = self.cursor.execute(f"SELECT * FROM {table}").fetchall()
            except sqlite3.Error as error:
                logging.info(error)

            data_from_table = [
                asdict(
                    eval("".join(word.capitalize() for word in table.split("_")))(*row)
                )
                for row in rows
            ]
            return data_from_table

        data = {}
        tables = ["genre", "person", "film_work", "genre_film_work", "person_film_work"]
        for table in tables:
            data_list = {f"{table}": get_data(table)}
            data.update(data_list)
        return data
