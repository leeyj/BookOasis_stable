# -*- coding: utf-8 -*-
import os
from repositories.trash_repository import TrashRepository

class TrashService:
    @staticmethod
    def get_deleted_books(db_type):
        """물리적으로 사라져서 휴지통(is_deleted=1)에 들어있는 도서 목록을 카테고리 정보와 함께 조회"""
        rows = TrashRepository.get_deleted_books(db_type)
        return [
            {
                'id': r['id'],
                'title': r['title'],
                'file_path': r['file_path'],
                'deleted_at': r['deleted_at'],
                'library_id': r['library_id'],
                'library_name': r['library_name'] or '미지정 카테고리'
            }
            for r in rows
        ]

    @staticmethod
    def restore_books(db_type, book_ids):
        """휴지통에 들어있는 특정 도서 목록을 다시 일반 상태(is_deleted=0)로 복구"""
        if not book_ids:
            return True
        try:
            return TrashRepository.restore_books(db_type, book_ids)
        except Exception as e:
            print(f"[TrashService ERROR] Failed to restore books: {e}")
            return False

    @staticmethod
    def empty_trash(db_type, library_id=None, book_ids=None):
        """휴지통 비우기 (일괄 또는 선택적 영구 삭제)"""
        try:
            # 1. 대상 도서 ID 목록 확보
            if book_ids:
                target_ids = book_ids
            elif library_id:
                target_ids = TrashRepository.get_deleted_book_ids_by_library(db_type, library_id)
            else:
                target_ids = TrashRepository.get_all_deleted_book_ids(db_type)
                
            if not target_ids:
                return True
                
            # 1.5. 물리적 커버 이미지 파일 소거 준비
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            covers_dir = os.path.join(base_dir, 'covers')
            
            # 2. 관련 진척도 및 로그 데이터 하드 딜리트 트랜잭션 구동
            for i in range(0, len(target_ids), 900):
                chunk = target_ids[i:i+900]
                
                # 2.1. 삭제 대상 도서들의 커버 이미지 정보 사전 로드
                cover_images = TrashRepository.fetch_book_covers(db_type, chunk)
                target_covers = sorted(set(cover_images))
                
                # DB 및 종속 테이블 완전 삭제 수행 & 참조 없는 커버 리스트 리턴
                unreferenced_covers = TrashRepository.hard_delete_books_transaction(db_type, chunk, target_covers)
                
                # 2.2. 로컬 정적 커버 파일 삭제
                for cover_img in unreferenced_covers:
                    cover_path = os.path.join(covers_dir, cover_img)
                    if os.path.exists(cover_path) and os.path.isfile(cover_path):
                        try:
                            os.remove(cover_path)
                            print(f"[TrashService] Physically deleted unreferenced cover: {cover_path}")
                        except Exception as ex_file:
                            print(f"[TrashService WARNING] Failed to delete cover file '{cover_path}': {ex_file}")
                 
            print(f"[TrashService] Successfully hard deleted {len(target_ids)} books from DB and storage.")
            return True
        except Exception as e:
            print(f"[TrashService ERROR] Failed to empty trash: {e}")
            return False
