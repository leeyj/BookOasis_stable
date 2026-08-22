# -*- coding: utf-8 -*-
"""
gdrive_copy_service.py – 구글 드라이브 공유 폴더를 사용자 자신의 드라이브로
서버사이드 복사(files.copy)한 뒤, 대상 카테고리(이미 등록된, 서버사이드 복사
리모트/목적지 경로가 설정된 로컬/마운트 카테고리)를 재스캔하는 백그라운드 작업
(scanner_queue task_type: gdrive_copy).

대상 카테고리는 매번 새로 만들지 않는다 — 관리자가 "카테고리 추가/수정" 모달에서
미리 리모트/목적지 경로를 설정해둔 카테고리(physical_path가 그 리모트/경로의 실제
로컬 마운트 지점) 중에서 선택해 반복적으로 새 파일만 추가 복사하는 방식이다.
"""
import database
from repositories.category_repository import CategoryRepository
from repositories.scanner_queue_repository import ScannerQueueRepository
from utils.drive_helper import fetch_gdrive_folder_files, has_gdrive_share_line
from utils.rclone_gdrive_copy import get_access_token, resolve_dest_folder, find_or_create_folder, copy_file


class GdriveCopyService:
    @staticmethod
    def parse_source_links(raw_links):
        """textarea 원문에서 줄 단위로 공유 폴더 링크/ID를 추출."""
        links = []
        for line in str(raw_links or '').replace('\r', '').splitlines():
            line = line.strip()
            if line:
                links.append(line)
        return links

    @staticmethod
    def start_gdrive_copy_job(db_type, library_id, source_links):
        from services.scanner_queue import scanner_queue

        try:
            library_id = int(library_id)
        except (TypeError, ValueError):
            raise ValueError('대상 카테고리를 선택해 주세요.')

        library = CategoryRepository.get_library_by_id(db_type, library_id)
        if not library:
            raise ValueError('대상 카테고리를 찾을 수 없습니다.')
        if not library.get('gdrive_copy_remote'):
            raise ValueError('선택한 카테고리에 서버사이드 복사 대상 리모트가 설정되어 있지 않습니다. 카테고리 수정에서 먼저 설정해 주세요.')
        if has_gdrive_share_line(library.get('physical_path')):
            raise ValueError('구글 드라이브 공유 링크가 포함된 카테고리는 책을 열람할 때 자동으로 복사되므로, 이 일괄 복사 기능의 대상으로 선택할 수 없습니다.')

        links = GdriveCopyService.parse_source_links(source_links)
        if not links:
            raise ValueError('구글 드라이브 공유 폴더 링크를 입력해 주세요.')

        enqueued = scanner_queue.enqueue(
            'gdrive_copy',
            db_type=db_type,
            library_id=library_id,
            source_links=links,
        )
        if not enqueued:
            raise ValueError('이 카테고리에 대한 복사 작업이 이미 진행 중이거나 대기 중입니다.')
        return True

    @staticmethod
    def run_gdrive_copy_job(sq, task_id, db_type='general', library_id=None, source_links=None):
        from services.scanner_queue import ScanCancelledError, scanner_queue

        source_links = source_links or []

        library = CategoryRepository.get_library_by_id(db_type, library_id)
        if not library:
            raise RuntimeError(f'카테고리(id={library_id})를 찾을 수 없습니다 (삭제되었을 수 있음).')

        remote = library.get('gdrive_copy_remote')
        dest_path = library.get('gdrive_copy_dest_path') or ''
        local_scan_path = library.get('physical_path')
        if not remote:
            raise RuntimeError('카테고리에 서버사이드 복사 대상 리모트가 설정되어 있지 않습니다.')

        sq.log(f"[GdriveCopy] 시작: library='{library.get('name')}', remote='{remote}', dest_path='{dest_path}', links={len(source_links)}개")

        access_token = get_access_token(remote)
        dest_root_folder_id = resolve_dest_folder(access_token, dest_path)

        # 1. 소스 폴더(들)의 파일 목록 수집
        ScannerQueueRepository.update_task_status(task_id, 'running', stage='소스 폴더 목록 조회 중...')
        all_items = []
        for link in source_links:
            all_items.extend(fetch_gdrive_folder_files(link))

        total = len(all_items)
        if total == 0:
            raise RuntimeError('복사할 파일을 찾지 못했습니다 (지원 확장자: zip/cbz/rar/cbr/epub/pdf/txt/yaml/xml/json).')

        # 2. 목적지 하위 폴더 트리 준비 (rel_folder별 캐시)
        folder_cache = {'': dest_root_folder_id}

        def resolve_rel_folder(rel_folder):
            rel_folder = (rel_folder or '').strip('/\\').replace('\\', '/')
            if rel_folder in folder_cache:
                return folder_cache[rel_folder]
            parent_id = dest_root_folder_id
            parts = [p for p in rel_folder.split('/') if p]
            built = ''
            for part in parts:
                built = f'{built}/{part}' if built else part
                if built in folder_cache:
                    parent_id = folder_cache[built]
                    continue
                parent_id = find_or_create_folder(access_token, part, parent_id)
                folder_cache[built] = parent_id
            return parent_id

        # 3. 파일 순회 복사
        copied = 0
        failed = []
        for i, item in enumerate(all_items, start=1):
            if ScannerQueueRepository.is_cancel_requested(task_id):
                raise ScanCancelledError('사용자 요청으로 Drive 복사가 중지되었습니다.')

            filename = item.get('name', '')
            ScannerQueueRepository.update_task_status(
                task_id, 'running', stage=f'{i}/{total} 파일 복사 중 ({filename})'
            )
            try:
                dest_folder_id = resolve_rel_folder(item.get('rel_folder', ''))
                copy_file(access_token, item['id'], dest_folder_id, dest_name=filename)
                copied += 1
            except Exception as copy_err:
                sq.log(f"[GdriveCopy] 파일 복사 실패 ({filename}): {copy_err}")
                failed.append(filename)

        summary = f'{copied}/{total} 파일 복사 완료' + (f' ({len(failed)}개 실패)' if failed else '')
        ScannerQueueRepository.update_task_status(task_id, 'running', stage=summary)
        sq.log(f"[GdriveCopy] {summary}")

        if copied == 0:
            raise RuntimeError(f'모든 파일 복사에 실패했습니다: {", ".join(failed[:5])}')

        # 4. 기존 카테고리 재스캔 트리거
        db_path = database.get_db_path(db_type)
        scanner_queue.enqueue(
            'library_scan', db_type=db_type, db_path=db_path, library_id=library_id,
            physical_path=local_scan_path, force=False, trigger_type='manual', is_cron=False,
        )
        sq.log(f"[GdriveCopy] 카테고리 #{library_id} 스캔 큐 등록 완료")
