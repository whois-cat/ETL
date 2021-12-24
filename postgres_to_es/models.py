from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel


class Genre(BaseModel):
    id: UUID
    name: str


class Person(BaseModel):
    id: UUID
    full_name: str
    role: List[str]
    film_ids: List[UUID]


class FilmWork(BaseModel):
    id: UUID
    imdb_rating: Optional[float]
    genre: List[dict[str, str]]
    title: str
    description: Optional[str]
    director: Optional[Person]
    actors_names: List[str]
    writers_names: List[str]
    actors: List[Person]
    writers: List[Person]
