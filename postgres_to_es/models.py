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
    director: Optional[Person]
    actors_names: list[str]
    writers_names: list[str]
    actors: list[Person]
    writers: list[Person]


class ShortInfoPerson(BaseModel):
    id: uuid.UUID
    role: str
    title: str
    film_work_id: uuid.UUID


class ShortInfoGenre(BaseModel):
    id: uuid.UUID
    title: str
    film_work_id: uuid.UUID


class Person(BaseModel):
    id: uuid.UUID
    full_name: str
    films: list[ShortInfoPerson]


class Genre(BaseModel):
    id: str
    name: str
    films: list[ShortInfoGenre]