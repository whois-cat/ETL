from typing import Optional
import uuid
from pydantic import BaseModel


class Person(BaseModel):
    id: uuid.UUID
    name: str


class FilmWork(BaseModel):
    id: uuid.UUID
    imdb_rating: Optional[float]
    genre: list[str]
    title: str
    description: Optional[str]
    director: Optional[str]
    actors_names: list[str]
    writers_names: list[str]
    actors: list[Person]
    writers: list[Person]
