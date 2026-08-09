from repositories.collection_repository import CollectionRepository
from repositories.book_repository import BookRepository

class CollectionService:
    @staticmethod
    def create_collection(db_type, user_id, name, description=None, color='#7c3aed', cover_image=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError("컬렉션 이름을 입력해 주세요.")
        if len(name) > 50:
            raise ValueError("컬렉션 이름은 50자를 초과할 수 없습니다.")
        return CollectionRepository.create_collection(db_type, user_id, name, description, color, cover_image)

    @staticmethod
    def get_user_collections(db_type, user_id):
        return CollectionRepository.get_user_collections(db_type, user_id)

    @staticmethod
    def get_collection_detail(db_type, collection_id, user_id):
        coll = CollectionRepository.get_collection_by_id(db_type, collection_id, user_id=user_id)
        if not coll:
            raise ValueError("컬렉션을 찾을 수 없거나 접근 권한이 없습니다.")

        items = CollectionRepository.get_collection_items(db_type, collection_id)
        
        # Enrich items (if series_name item, fetch series representative cover & book count)
        enriched_items = []
        for item in items:
            item_dict = dict(item)
            if item.get('series_name'):
                s_name = item['series_name']
                series_books = BookRepository.get_books_by_series(db_type, s_name, user_id=user_id)
                book_count = len(series_books) if series_books else 0
                rep_cover = None
                rep_format = 'zip'
                if series_books:
                    for b in series_books:
                        if b.get('cover_image'):
                            rep_cover = b['cover_image']
                            break
                    rep_format = series_books[0].get('file_format') or 'zip'
                item_dict['title'] = s_name
                item_dict['type'] = 'series'
                item_dict['book_count'] = book_count
                item_dict['cover_image'] = rep_cover
                item_dict['file_format'] = rep_format
            elif item.get('book_id'):
                item_dict['title'] = item.get('book_title')
                item_dict['type'] = 'book'
                item_dict['cover_image'] = item.get('book_cover')
                item_dict['file_format'] = item.get('book_format') or 'text'
            elif item.get('audiobook_id'):
                item_dict['title'] = item.get('audiobook_title')
                item_dict['type'] = 'audiobook'
                item_dict['cover_image'] = item.get('audiobook_poster')
                item_dict['file_format'] = 'audiobook'

            enriched_items.append(item_dict)

        coll['items'] = enriched_items
        return coll

    @staticmethod
    def update_collection(db_type, collection_id, user_id, name, description=None, color='#7c3aed', cover_image=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError("컬렉션 이름을 입력해 주세요.")
        return CollectionRepository.update_collection(db_type, collection_id, user_id, name, description, color, cover_image)

    @staticmethod
    def delete_collection(db_type, collection_id, user_id):
        return CollectionRepository.delete_collection(db_type, collection_id, user_id)

    @staticmethod
    def add_item(db_type, collection_id, user_id, book_id=None, series_name=None, audiobook_id=None):
        coll = CollectionRepository.get_collection_by_id(db_type, collection_id, user_id=user_id)
        if not coll:
            raise ValueError("컬렉션을 찾을 수 없거나 접근 권한이 없습니다.")
        return CollectionRepository.add_item_to_collection(db_type, collection_id, book_id, series_name, audiobook_id)

    @staticmethod
    def remove_item(db_type, collection_id, user_id, item_id):
        coll = CollectionRepository.get_collection_by_id(db_type, collection_id, user_id=user_id)
        if not coll:
            raise ValueError("컬렉션을 찾을 수 없거나 접근 권한이 없습니다.")
        return CollectionRepository.remove_item_from_collection(db_type, collection_id, item_id)
