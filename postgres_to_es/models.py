import uuid
from typing import Optional

from pydantic import BaseModel


class PersonRole(BaseModel):
    id: uuid.UUID
    name: str


class FilmWork(BaseModel):
    id: uuid.UUID
    imdb_rating: Optional[float]
    genre: list[dict[str, str]]
    title: str
    description: Optional[str]
    director: Optional[PersonRole]
    actors_names: list[str]
    writers_names: list[str]
    actors: list[PersonRole]
    writers: list[PersonRole]


class FilmWorkShort(BaseModel):
    id: uuid.UUID
    title: str
    film_work_id: uuid.UUID


class FilmWorkShortWithRole(FilmWorkShort):
    role: str


class Person(BaseModel):
    id: uuid.UUID
    full_name: str
    films: list[FilmWorkShortWithRole]


class Genre(BaseModel):
    id: str
    name: str
    films: list[FilmWorkShort]