import uuid
from typing import Optional

from pydantic import BaseModel


class Person(BaseModel):
    id: uuid.UUID
    name: str


class FilmWork(BaseModel):
    id: uuid.UUID
    imdb_rating: Optional[float]
    genre: list[dict[str, str]]
    title: str
    description: Optional[str]
    director: list[Person]
    actors_names: list[str]
    writers_names: list[str]
    actors: list[Person]
    writers: list[Person]
