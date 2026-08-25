# -*- coding: utf-8 -*-
"""
gdrive_copy_service.py – 구글 드라이브 공유 폴더를 사용자 자신의 드라이브로
서버사이드 복사(rclone CLI backend copyid)해 지정한 로컬 폴더에 내려받는 백그라운드
작업(scanner_queue task_type: gdrive_copy).

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
    rclone_copy_file_by_id,
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
    def start_gdrive_copy_job(db_type, remote, dest_local_path, source_links, rclone_rc_url=None, mount_root_override=None):
        from services.scanner_queue import scanner_queue

        remote = str(remote or '').strip()
        dest_local_path = str(dest_local_path or '').strip()
        mount_root_override = str(mount_root_override or '').strip()
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
            mount_root_override=mount_root_override,
            source_links=links,
        )
        if not enqueued:
            raise ValueError('이 폴더에 대한 복사 작업이 이미 진행 중이거나 대기 중입니다.')
        return True

    @staticmethod
    def run_gdrive_copy_job(sq, task_id, db_type='general', remote=None, dest_local_path=None, rclone_rc_url=None, mount_root_override=None, source_links=None):
        from services.scanner_queue import ScanCancelledError

        source_links = source_links or []

        if not remote:
            raise RuntimeError('연결할 리모트가 지정되지 않았습니다.')
        if not dest_local_path:
            raise RuntimeError('저장할 로컬 폴더 경로가 지정되지 않았습니다.')

        # dest_path(Drive 쪽 목적지 폴더)는 관리자가 손으로 입력하지 않고, 저장할 로컬
        # 폴더에서 "마운트 루트"를 뺀 나머지로 매번 새로 계산한다 — 손으로 입력한 두 값이
        # 겹치는 부분을 착각해 어긋나는 게 실사용자 혼란 포인트였음(2026-08-22). 마운트
        # 루트 자체도 기본적으로는 관리자가 입력하지 않는다 — /proc/mounts(OS 마운트
        # 테이블, 우선)나 rclone RC의 mount/listmounts(등록된 경우만, 폴백)로 실시간
        # 감지한다. 단, 도커 환경에서는 이 서버와 rclone RC 서버가 서로 다른 파일시스템
        # 관점(볼륨 매핑)을 가져 두 방법 모두 원천적으로 실패할 수 있어(2026-08-24 실사용자
        # 리포트), mount_root_override가 주어지면 감지를 건너뛰고 그대로 신뢰한다.
        mount_root_override = str(mount_root_override or '').strip()
        if mount_root_override:
            mount_root = mount_root_override
            sq.log(f"[GdriveCopy] 마운트 루트 수동 입력값 사용: '{mount_root}' (자동 감지 건너뜀)")
        else:
            from tools.scanner.vfs import detect_mount_root, resolve_rc_urls
            rc_urls = resolve_rc_urls(db_type, {'rclone_rc_url': rclone_rc_url or ''})
            mount_root = detect_mount_root(remote, dest_local_path, rc_urls)
            if not mount_root:
                sq.log(f"[GdriveCopy] 경고: 마운트 루트 자동 감지 실패 — dest_path를 Drive 루트 기준으로 계산합니다. 도커 환경이라면 마운트 루트를 직접 입력해 주세요.")
        raw_dest_path = compute_relative_dest_path(dest_local_path, mount_root)
        if mount_root and raw_dest_path is None:
            sq.log(f"[GdriveCopy] 경고: dest_local_path='{dest_local_path}'가 감지된 마운트 루트 '{mount_root}' 하위 경로가 아닙니다 — dest_path를 Drive 루트 기준으로 계산합니다. 심볼릭 링크/대소문자/도커 볼륨 매핑 차이를 확인해 주세요.")
        dest_path = raw_dest_path or ''

        sq.log(f"[GdriveCopy] 시작: remote='{remote}', dest_local_path='{dest_local_path}', dest_path='{dest_path}', links={len(source_links)}개")

        # 1. 소스 폴더(들)의 파일 목록 수집
        ScannerQueueRepository.update_task_status(task_id, 'running', stage='소스 폴더 목록 조회 중...')
        all_items = []
        for link in source_links:
            all_items.extend(fetch_gdrive_folder_files(link))

        total = len(all_items)
        if total == 0:
            raise RuntimeError('복사할 파일을 찾지 못했습니다 (지원 확장자: zip/cbz/rar/cbr/epub/pdf/txt/yaml/xml/json).')

        # 2. 파일 순회 복사 — rclone CLI(backend copyid)로 목적지를 'remote:path' 문법으로
        # 직접 지정한다(gdrive_view_copy_service.py와 동일 방식, 2026-08-25). 예전 REST
        # API(files.copy) 방식은 Drive 쪽 시작 폴더를 root_folder_id/마운트 서브경로
        # 자동 감지로 우리가 직접 추론해야 했는데, 이 감지가 도커에서 실패하면(/proc/mounts를
        # 못 읽음) 관리자가 로컬 마운트 루트를 수동 입력해도 소용없이 복사된 파일이 로컬에서
        # 보이는 마운트 서브트리 바깥에 생기는 버그가 있었다(커뮤니티 리포트). rclone CLI는
        # 자신의 rclone.conf 설정(root_folder_id 포함)을 그대로 써서 이 추론이 필요 없다.
        copied = 0
        failed = []
        for i, item in enumerate(all_items, start=1):
            if ScannerQueueRepository.is_cancel_requested(task_id):
                raise ScanCancelledError('사용자 요청으로 Drive 복사가 중지되었습니다.')

            filename = item.get('name', '')
            ScannerQueueRepository.update_task_status(
                task_id, 'running', stage=f'{i}/{total} 파일 복사 중 ({filename})'
            )
            rel_folder = (item.get('rel_folder') or '').strip('/\\').replace('\\', '/')
            segments = [s for s in (dest_path, rel_folder, filename) if s]
            dest_rclone_path = f"{remote}:{'/'.join(segments)}"
            try:
                rclone_copy_file_by_id(remote, item['id'], dest_rclone_path)
                copied += 1
            except Exception as copy_err:
                sq.log(f"[GdriveCopy] 파일 복사 실패 ({filename}): {copy_err}")
                failed.append(filename)

        summary = f'{copied}/{total} 파일 복사 완료' + (f' ({len(failed)}개 실패)' if failed else '')
        ScannerQueueRepository.update_task_status(task_id, 'running', stage=summary)
        sq.log(f"[GdriveCopy] {summary} — dest_local_path='{dest_local_path}'. 이 폴더를 가리키는 카테고리를 만들면(또는 이미 있다면 재스캔하면) 목록에 반영됩니다.")

        if copied == 0:
            raise RuntimeError(f'모든 파일 복사에 실패했습니다: {", ".join(failed[:5])}')
