from django.contrib import admin

from .models import FilmWork, FilmWorkGenre, FilmWorkPerson, Genre, Person


class FilmWorkGenreInline(admin.TabularInline):
    model = FilmWorkGenre


class FilmWorkPersonInline(admin.TabularInline):
    model = FilmWorkPerson


@admin.register(FilmWork)
class FilmworkAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'rating',)
    fields = (
            'title', 'type', 'description', 'creation_date', 'certificate',
            'file_path', 'rating',
    )
    inlines = [
        FilmWorkGenreInline,
        FilmWorkPersonInline,
    ]
    search_fields = ('title', 'rating', 'description')
    ordering = ('title', 'rating', )



@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', )
    fields = ('name', 'description', )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('full_name', )
    fields = ('full_name', 'birth_date', )
    search_fields = ('full_name', )
    ordering = ('full_name',)




