# -*- coding: utf-8 -*-
from repositories.book_repository import BookRepository

class LibraryService:
    @staticmethod
    def get_media_tags(db_type, library_id=None):
        tags_raw = BookRepository.get_media_tags(db_type, library_id)

        unique_tags = set()
        for r in tags_raw:
            if r:
                for tag in str(r).split(','):
                    clean_tag = tag.strip()
                    if clean_tag:
                        unique_tags.add(clean_tag)

        return sorted(unique_tags)

    @staticmethod
    def get_media_genres(db_type, library_id=None):
        genres_raw = BookRepository.get_media_genres(db_type, library_id)

        unique_genres = set()
        for r in genres_raw:
            if r:
                for genre in str(r).split(','):
                    clean_genre = genre.strip()
                    if clean_genre:
                        unique_genres.add(clean_genre)

        return sorted(unique_genres)
