# -*- coding: utf-8 -*-
import database
from repositories.category_repository import CategoryRepository

class CategoryService:
    @staticmethod
    def get_libraries(db_type, user_id=None, role=None):
        if user_id and role != 'admin':
            rows = CategoryRepository.get_libraries_by_user_permissions(db_type, user_id)
        else:
            rows = CategoryRepository.get_all_libraries(db_type)
            
        return [{
            'id': r['id'], 
            'name': r['name'], 
            'physical_path': r['physical_path'],
            'is_remote': r['is_remote'] or 0,
            'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
            'rclone_rc_url': r['rclone_rc_url'] or '',
            'icon': r['icon'] or 'fa-book',
            'color': r['color'] or '#94a3b8'
        } for r in rows]

    @staticmethod
    def _clean_physical_path(raw_path):
        if not raw_path: return ""
        lines = [line.strip() for line in str(raw_path).replace('\r', '').split('\n')]
        return '\n'.join([line for line in lines if line])

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8'):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 100자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        return CategoryRepository.add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color)

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8'):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 25자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        CategoryRepository.edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color)

    @staticmethod
    def delete_library(db_type, library_id):
        # 관련 리포트 파일 연쇄 영구 소거
        try:
            from utils.report_helper import delete_all_reports
            delete_all_reports(library_id)
        except Exception as e:
            print(f"[CategoryService ERROR] Bulk report file removal failed: {e}")

        CategoryRepository.delete_library(db_type, library_id)

        # 대량 삭제(Delete) 완료 후 물리 공간 회수 및 DB 성능 향상을 위해 백그라운드로 튜닝 구동
        import threading
        t = threading.Thread(target=database.optimize_database, args=(db_type,))
        t.daemon = True
        t.start()
