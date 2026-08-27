# -*- coding: utf-8 -*-
"""로컬 디스크 카테고리 경로의 파일 이벤트(생성/삭제/이동)를 감지해
자동으로 라이브러리 스캔을 큐에 넣는 플러그인.

- 순수 로컬 디스크 전용이다. rclone/gdrive 등 원격 마운트 라이브러리(is_remote)는
  대상에서 제외한다 — 그 경로는 기존 lazy_scan 폴링 + 3rd party rclone 플러그인이
  이미 담당한다.
- 실제 검색/메타데이터 적용 기능은 없는 유틸리티 플러그인이다(search/apply는 stub).
- 삭제된 파일 정리는 기존 스캔 로직(services/book_scan_service.py)이 스캔 시점에
  os.path.exists로 이미 처리하므로, 이 플러그인은 이벤트 발생 시 해당 라이브러리의
  스캔을 큐에 넣는 것만 담당한다.
"""
import os
import threading
import time

from plugins.metadata.base import BaseMetadataProvider

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - 커스텀 이미지 등 예외적 환경 대비
    Observer = None
    FileSystemEventHandler = object
    _WATCHDOG_IMPORT_ERROR = str(exc)

_WATCHED_SESSIONS = ('general', 'adult', 'audiobook', 'video')


class LocalFolderWatchMetadataProvider(BaseMetadataProvider):
    """Sample plugin: watch local library folders and trigger scans on change."""

    id = "local_folder_watch"
    name = "로컬 폴더 실시간 감지"
    is_searchable = False
    category_tab = {"sessions": "all"}
    config_schema = [
        {
            "key": "ENABLE_LOCAL_WATCH",
            "label": "로컬 폴더 실시간 감지 활성화",
            "type": "checkbox",
            "default": False,
            "description": "활성화하면 로컬 디스크 라이브러리 경로의 파일 변경을 감지해 자동으로 스캔을 큐에 넣습니다. 원격(rclone/gdrive) 라이브러리는 대상에서 제외됩니다.",
        },
        {
            "key": "DEBOUNCE_SECONDS",
            "label": "디바운스 대기시간(초)",
            "type": "number",
            "default": 5,
            "description": "같은 라이브러리에서 연속 발생하는 이벤트를 이 시간만큼 조용해질 때까지 모아 스캔 1회로 합칩니다.",
        },
        {
            "key": "POLL_INTERVAL_SECONDS",
            "label": "설정 재확인 주기(초)",
            "type": "number",
            "default": 30,
            "description": "활성화 여부/라이브러리 목록 변경을 다시 확인하는 주기입니다. 앱 재시작 없이도 이 주기 안에 변경사항이 반영됩니다.",
        },
    ]

    _service_started = False
    _service_lock = threading.Lock()

    def search(self, db_type, query):
        return []

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 메타데이터 적용을 지원하지 않습니다."

    # ------------------------------------------------------------------
    # config helpers
    # ------------------------------------------------------------------
    def _get_config(self, db_type):
        return self.get_plugin_config(db_type, default={}) or {}

    def _is_enabled(self, db_type):
        cfg = self._get_config(db_type)
        raw = cfg.get("ENABLE_LOCAL_WATCH", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "y", "yes", "on")

    def _debounce_seconds(self, db_type):
        cfg = self._get_config(db_type)
        try:
            v = float(cfg.get("DEBOUNCE_SECONDS", 5))
        except Exception:
            v = 5.0
        return max(1.0, min(120.0, v))

    def _poll_interval_seconds(self, db_type):
        cfg = self._get_config(db_type)
        try:
            v = float(cfg.get("POLL_INTERVAL_SECONDS", 30))
        except Exception:
            v = 30.0
        return max(5.0, min(600.0, v))

    # ------------------------------------------------------------------
    # background service lifecycle
    # ------------------------------------------------------------------
    def start_background_service(self, db_type):
        if Observer is None:
            print(f"[{self.id}] watchdog 라이브러리를 불러올 수 없어 비활성화됩니다: {_WATCHDOG_IMPORT_ERROR}")
            return None

        with LocalFolderWatchMetadataProvider._service_lock:
            if LocalFolderWatchMetadataProvider._service_started:
                return None
            LocalFolderWatchMetadataProvider._service_started = True

        thread = threading.Thread(target=self._run_loop, name="local-folder-watch", daemon=True)
        thread.start()
        return None

    def _run_loop(self):
        observer = Observer()
        observer.start()
        # {(session, library_id): {'watch': ObservedWatch, 'path': str}}
        active = {}

        try:
            while True:
                try:
                    self._reconcile(observer, active)
                except Exception as exc:
                    print(f"[{self.id}] 감시 대상 갱신 실패: {exc}")

                interval = self._poll_interval_seconds('general')
                time.sleep(interval)
        finally:
            observer.stop()
            observer.join(timeout=5)

    def _reconcile(self, observer, active):
        from repositories.category_repository import CategoryRepository

        if not self._is_enabled('general'):
            for key, entry in list(active.items()):
                observer.unschedule(entry['watch'])
                del active[key]
            return

        debounce_seconds = self._debounce_seconds('general')
        desired = {}
        for session in _WATCHED_SESSIONS:
            try:
                libraries = CategoryRepository.get_all_libraries(session)
            except Exception as exc:
                print(f"[{self.id}] '{session}' 라이브러리 목록 조회 실패: {exc}")
                continue

            for lib in libraries:
                if lib.get('is_remote'):
                    continue
                physical_path = str(lib.get('physical_path') or '').strip()
                if not physical_path or not os.path.isdir(physical_path):
                    continue
                desired[(session, lib.get('id'))] = physical_path

        # 사라졌거나 경로가 바뀐 항목은 감시 해제
        for key in list(active.keys()):
            if key not in desired or active[key]['path'] != desired[key]:
                observer.unschedule(active[key]['watch'])
                del active[key]

        # 새로 추가되었거나 경로가 바뀐 항목은 감시 등록
        for key, physical_path in desired.items():
            if key in active:
                continue
            session, library_id = key
            handler = _DebouncedScanHandler(
                session=session,
                library_id=library_id,
                physical_path=physical_path,
                debounce_seconds=debounce_seconds,
            )
            watch = observer.schedule(handler, physical_path, recursive=True)
            active[key] = {'watch': watch, 'path': physical_path}


class _DebouncedScanHandler(FileSystemEventHandler):
    """라이브러리 하나에 대한 이벤트를 모아서 조용해지면 스캔 1회를 큐에 넣는다."""

    def __init__(self, session, library_id, physical_path, debounce_seconds):
        self.session = session
        self.library_id = library_id
        self.physical_path = physical_path
        self.debounce_seconds = debounce_seconds
        self._timer = None
        self._lock = threading.Lock()

    def on_any_event(self, event):
        if getattr(event, 'is_directory', False) and event.event_type == 'modified':
            # 디렉토리 자체의 modified 이벤트는 노이즈가 많아 무시(파일 이벤트로 충분히 감지됨)
            return

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._trigger_scan)
            self._timer.daemon = True
            self._timer.start()

    def _trigger_scan(self):
        try:
            import database
            from services.scanner_queue import scanner_queue

            scanner_queue.enqueue(
                'library_scan',
                db_type=self.session,
                db_path=database.get_db_path(self.session),
                library_id=self.library_id,
                physical_path=self.physical_path,
                force=False,
                force_requeue=True,
                trigger_type='plugin_watch',
                is_cron=False,
            )
            print(f"[local_folder_watch] 파일 변경 감지 -> 스캔 큐 등록: session={self.session} library_id={self.library_id}")
        except Exception as exc:
            print(f"[local_folder_watch] 스캔 큐 등록 실패: session={self.session} library_id={self.library_id} error={exc}")
