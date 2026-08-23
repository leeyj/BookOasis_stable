# -*- coding: utf-8 -*-
"""
gdrive_copy_service.py – 구글 드라이브 공유 폴더를 사용자 자신의 드라이브로
서버사이드 복사(files.copy)해 지정한 로컬 폴더에 내려받는 백그라운드 작업
(scanner_queue task_type: gdrive_copy).

복사는 카테고리와 무관한 독립 동작이다 — "복사해온 파일을 카테고리로 등록해서
보여줄지"는 순전히 사용자 선택이라, 복사 대상 카테고리를 미리 만들어두게 강제할
이유가 없다(2026-08-23, 사용자 판단). 예전엔 사전에 리모트/목적지 경로를 설정해둔
카테고리를 골라야만 실행할 수 있었지만, 지금은 리모트 + 저장할 로컬 폴더만 있으면
바로 실행되고 완료 후 재스캔도 트리거하지 않는다 — 나중에 그 폴더를 가리키는 일반
카테고리를 만들면 평소처럼 스캔된다.
"""
from repositories.scanner_queue_repository import ScannerQueueRepository
from utils.drive_helper import fetch_gdrive_folder_files
from utils.rclone_gdrive_copy import (
    get_access_token,
    resolve_dest_folder,
    find_or_create_folder,
    copy_file,
    compute_relative_dest_path,
)


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
    def start_gdrive_copy_job(db_type, remote, dest_local_path, source_links, rclone_rc_url=None):
        from services.scanner_queue import scanner_queue

        remote = str(remote or '').strip()
        dest_local_path = str(dest_local_path or '').strip()
        if not remote:
            raise ValueError('연결할 리모트를 선택해 주세요.')
        if not dest_local_path:
            raise ValueError('저장할 로컬 폴더 경로를 입력해 주세요.')

        links = GdriveCopyService.parse_source_links(source_links)
        if not links:
            raise ValueError('구글 드라이브 공유 폴더 링크를 입력해 주세요.')

        enqueued = scanner_queue.enqueue(
            'gdrive_copy',
            db_type=db_type,
            remote=remote,
            dest_local_path=dest_local_path,
            rclone_rc_url=rclone_rc_url,
            source_links=links,
        )
        if not enqueued:
            raise ValueError('이 폴더에 대한 복사 작업이 이미 진행 중이거나 대기 중입니다.')
        return True

    @staticmethod
    def run_gdrive_copy_job(sq, task_id, db_type='general', remote=None, dest_local_path=None, rclone_rc_url=None, source_links=None):
        from services.scanner_queue import ScanCancelledError

        source_links = source_links or []

        if not remote:
            raise RuntimeError('연결할 리모트가 지정되지 않았습니다.')
        if not dest_local_path:
            raise RuntimeError('저장할 로컬 폴더 경로가 지정되지 않았습니다.')

        # dest_path(Drive 쪽 목적지 폴더)는 관리자가 손으로 입력하지 않고, 저장할 로컬
        # 폴더에서 "마운트 루트"를 뺀 나머지로 매번 새로 계산한다 — 손으로 입력한 두 값이
        # 겹치는 부분을 착각해 어긋나는 게 실사용자 혼란 포인트였음(2026-08-22). 마운트
        # 루트 자체도 관리자가 입력하지 않는다 — /proc/mounts(OS 마운트 테이블, 우선)나
        # rclone RC의 mount/listmounts(등록된 경우만, 폴백)로 실시간 감지한다.
        from tools.scanner.vfs import detect_mount_root, resolve_rc_urls
        rc_urls = resolve_rc_urls(db_type, {'rclone_rc_url': rclone_rc_url or ''})
        mount_root = detect_mount_root(remote, dest_local_path, rc_urls)
        dest_path = compute_relative_dest_path(dest_local_path, mount_root) or ''

        sq.log(f"[GdriveCopy] 시작: remote='{remote}', dest_local_path='{dest_local_path}', dest_path='{dest_path}', links={len(source_links)}개")

        access_token = get_access_token(remote)
        dest_root_folder_id = resolve_dest_folder(access_token, dest_path, remote)

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
        sq.log(f"[GdriveCopy] {summary} — dest_local_path='{dest_local_path}'. 이 폴더를 가리키는 카테고리를 만들면(또는 이미 있다면 재스캔하면) 목록에 반영됩니다.")

        if copied == 0:
            raise RuntimeError(f'모든 파일 복사에 실패했습니다: {", ".join(failed[:5])}')
