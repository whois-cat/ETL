import logging
import os

import psycopg2
from psycopg2.extensions import connection as _connection


class PostgresSaver:
    def __init__(self, psql_conn: _connection):
        self.connection = psql_conn
        self.cursor = self.connection.cursor()

    def create_tables(self):
        path = os.path.abspath(
            os.path.join(__file__, "../..", "schema_design", "postgres_schema.sql")
        )
        self.cursor.execute(open(f"{path}", "r").read())
        logging.info("Schema was created.")
        self.connection.commit()

    def save_all_data(self, data):
        for table in data:
            for data_table in data[table]:
                columns_names = data_table.keys()

                try:
                    self.cursor.execute(
                        "INSERT into content.{0} ({1}) VALUES ({2}) ON CONFLICT (id) DO NOTHING".format(
                            table,
                            ", ".join(columns_names),
                            ", ".join("%s" for _ in range(len(columns_names))),
                        ),
                        tuple(data_table.values()),
                    )
                except psycopg2.DatabaseError as error:
                    logging.exception(error)
                    self.cursor.execute(
                        "select * from pg_tables where schemaname='content';"
                    )
                    if not bool(self.cursor.rowcount):
                        self.create_tables()


            logging.info(
                f"Data from {table} was migrated."
            )
        self.connection.commit()
