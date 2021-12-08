import sys

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Q
from django.http import JsonResponse
from django.views.generic.detail import BaseDetailView
from django.views.generic.list import BaseListView

sys.path.append("movies")
from movies.models import FilmWork, PersonRoleType


class MoviesApiMixin:
    model = FilmWork
    http_method_names = ["get"]

    def _aggregate_person(role: str):
        return ArrayAgg(
            "filmworkperson__person_id__full_name",
            filter=Q(filmworkperson__role=role),
            distinct=True,
        )

    @classmethod
    def get_queryset(cls):
        return FilmWork.objects.select_related('persons', 'film_genres').annotate(
            genres=ArrayAgg("film_genres__name", distinct=True),
            actors=cls._aggregate_person(role=PersonRoleType.ACTOR),
            directors=cls._aggregate_person(role=PersonRoleType.DIRECTOR),
            writers=cls._aggregate_person(role=PersonRoleType.WRITER),
        ).values()

    @staticmethod
    def render_to_response(context, **response_kwargs):
        return JsonResponse(context)


class MoviesListApi(MoviesApiMixin, BaseListView):
    paginate_by = 50
    ordering = "title"

    def get_context_data(self, *, object_list=None, **kwargs):
        paginator, page, queryset, is_paginated = self.paginate_queryset(
            self.get_queryset(), self.paginate_by
        )
        return {
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "page": page.number,
            "prev": page.previous_page_number() if page.has_previous() else None,
            "next": page.next_page_number() if page.has_next() else None,
            "results": list(queryset),
        }


class MoviesDetailApi(MoviesApiMixin, BaseDetailView):
    def get_context_data(self, object, **kwargs):
        return object
