# -*- coding: utf-8 -*-
"""
library_scan_progress.py – 라이브러리 스캔의 진행 상황을 스캔 활동창에 보여줄 문구로 만드는 순수 로직.

예전에는 스캔 시작 시 큐 단계를 내부 문자열 'book_scan'으로 한 번 기록하고 스캔이 끝날 때까지 그대로 둬서,
수만 권을 스캔하는 내내 "book_scan"만 보였다. 스캐너 엔진(tools/scanner/engine.py)이 이 모듈의
LibraryScanProgress에 "폴더를 방문했다 / 이 폴더 처리가 끝났다"만 알려주면, 문구 만들기와 기록 빈도
제한(ThrottledStageReporter)은 여기서 처리한다. 엔진 쪽 수정을 최소화하고 로직을 단위 테스트할 수 있게
분리한 것이다.
"""
import os
import threading
import time


def format_library_scan_progress(phase, *, count=0, completed=0, total=0, current=''):
    """스캔 활동창에 보여줄 한 줄 진행 문구. 전체 경로는 노출하지 않고 폴더 이름만 쓴다."""
    if phase == 'discover':
        return f'폴더 탐색 중 · {max(0, int(count)):,}개 방문'

    total = max(0, int(total))
    completed = min(total, max(0, int(completed)))
    if total == 0:
        return '처리 대상 도서 파일 없음 · 마무리 중'

    percent = int(completed * 100 / total)
    remaining = total - completed
    stage = f'도서 파일 {completed:,}/{total:,} ({percent}%) · 남음 {remaining:,}권'
    if remaining == 0:
        return f'{stage} · DB 반영 중'
    current_name = os.path.basename(str(current or '').rstrip('/\\'))
    if current_name:
        stage = f'{stage} · {current_name}'
    return stage


def count_scan_units(filenames, media_extensions, image_extensions):
    """한 폴더의 진행 단위 수: 도서 파일 수, 도서 파일 없이 이미지만 있으면(이미지 폴더 책) 1권."""
    names = [str(name).lower() for name in (filenames or [])]
    media_count = sum(1 for name in names if name.endswith(tuple(media_extensions)))
    if media_count:
        return media_count
    return 1 if any(name.endswith(tuple(image_extensions)) for name in names) else 0


class LibraryScanProgress:
    """스캐너 엔진이 호출하는 진행 추적기. 콜백에서 예외가 나도 스캔에는 영향을 주지 않는다."""

    def __init__(self, callback=None):
        self._callback = callback if callable(callback) else None
        self._visited_folders = 0
        self._units_by_folder = {}
        self._finished_folders = set()
        self._completed = 0
        self._total = 0

    @property
    def completed(self):
        return self._completed

    @property
    def total(self):
        return self._total

    def _emit(self, phase, **details):
        if self._callback is None:
            return
        try:
            self._callback(phase, **details)
        except Exception as error:
            print(f"[Scanner-Progress] 진행 상태 갱신 실패(스캔은 계속 진행): {error}")

    def folder_visited(self, count=1):
        """폴더 순회(탐색) 단계: 방문한 폴더 수를 늘린다."""
        self._visited_folders += max(0, int(count))
        self._emit('discover', count=self._visited_folders)

    def start_processing(self, units_by_folder):
        """처리 단계 시작: 폴더별 도서 파일 수(진행 단위)를 받아 전체 수를 확정한다."""
        self._units_by_folder = {folder: max(0, int(units)) for folder, units in (units_by_folder or {}).items()}
        self._finished_folders = set()
        self._completed = 0
        self._total = sum(self._units_by_folder.values())
        self._emit('process', completed=0, total=self._total, current='')

    def finish(self, folder):
        """한 폴더의 처리가 끝났음을 알린다(변경 없음으로 건너뛴 폴더와 실패한 폴더도 포함). 같은 폴더는 한 번만 센다."""
        if folder in self._finished_folders or folder not in self._units_by_folder:
            return
        self._finished_folders.add(folder)
        self._completed += self._units_by_folder[folder]
        self._emit('process', completed=self._completed, total=self._total, current=folder)


class ThrottledStageReporter:
    """진행 문구를 큐 단계로 기록하되 너무 자주 쓰지 않는다(DB/Redis 쓰기 부하 방지).

    기록하는 경우: 단계가 바뀔 때(탐색→처리), 처리가 끝났을 때, 마지막 기록 후 interval 초가 지났을 때.
    같은 문구는 다시 쓰지 않는다. 스캔이 재시도로 처음부터 다시 시작할 때는 reset()으로 상태를 비운다.
    """

    def __init__(self, update_stage, interval=2.0, clock=time.monotonic):
        self._update_stage = update_stage
        self._interval = interval
        self._clock = clock
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._last_text = None
            self._last_phase = None
            self._last_written_at = None

    def __call__(self, phase, **details):
        text = format_library_scan_progress(phase, **details)
        total = int(details.get('total', 0) or 0)
        is_complete = phase == 'process' and total > 0 and int(details.get('completed', 0) or 0) >= total
        now = self._clock()
        with self._lock:
            if text == self._last_text:
                return
            due = (
                self._last_written_at is None
                or phase != self._last_phase
                or is_complete
                or now - self._last_written_at >= self._interval
            )
            if not due:
                return
            try:
                self._update_stage(text)
            except Exception as error:
                print(f"[Scanner-Progress] 단계 기록 실패(무시): {error}")
                return
            self._last_text = text
            self._last_phase = phase
            self._last_written_at = now
