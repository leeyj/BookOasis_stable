from utils.library_scan_progress import (
    LibraryScanProgress,
    ThrottledStageReporter,
    count_scan_units,
    format_library_scan_progress,
)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_discover_phase_text():
    assert format_library_scan_progress('discover', count=0) == '폴더 탐색 중 · 0개 방문'
    assert format_library_scan_progress('discover', count=12345) == '폴더 탐색 중 · 12,345개 방문'


def test_process_phase_shows_counts_percent_remaining_and_only_the_folder_name():
    text = format_library_scan_progress(
        'process', completed=250, total=1000, current='/mnt/library/만화/원피스/'
    )

    assert text == '도서 파일 250/1,000 (25%) · 남음 750권 · 원피스'
    assert '/mnt' not in text


def test_process_phase_when_everything_is_done_or_nothing_to_do():
    assert format_library_scan_progress('process', completed=40, total=40, current='x') == (
        '도서 파일 40/40 (100%) · 남음 0권 · DB 반영 중'
    )
    assert format_library_scan_progress('process', completed=0, total=0) == '처리 대상 도서 파일 없음 · 마무리 중'


def test_process_phase_clamps_out_of_range_values():
    assert format_library_scan_progress('process', completed=99, total=10).startswith('도서 파일 10/10')
    assert format_library_scan_progress('process', completed=-5, total=10).startswith('도서 파일 0/10')


def test_count_scan_units_counts_book_files_or_one_image_folder_book():
    media = ('.cbz', '.zip', '.epub')
    images = ('.jpg', '.png')

    assert count_scan_units(['a.CBZ', 'b.epub', 'cover.jpg', 'note.txt'], media, images) == 2
    assert count_scan_units(['001.jpg', '002.png'], media, images) == 1  # 이미지 폴더 책
    assert count_scan_units(['readme.txt'], media, images) == 0
    assert count_scan_units([], media, images) == 0


def test_tracker_counts_each_folder_once_including_skipped_and_failed_ones():
    events = []
    tracker = LibraryScanProgress(lambda phase, **details: events.append((phase, details)))

    tracker.folder_visited()
    tracker.folder_visited(3)
    tracker.start_processing({'/a': 2, '/b': 3, '/c': 0})
    tracker.finish('/a')
    tracker.finish('/a')  # 같은 폴더를 두 번 세지 않는다
    tracker.finish('/unknown')  # 계획에 없던 폴더는 무시
    tracker.finish('/b')
    tracker.finish('/c')

    assert [d['count'] for p, d in events if p == 'discover'] == [1, 4]
    process_events = [d for p, d in events if p == 'process']
    assert process_events[0] == {'completed': 0, 'total': 5, 'current': ''}
    assert [d['completed'] for d in process_events] == [0, 2, 5, 5]
    assert tracker.completed == tracker.total == 5


def test_tracker_without_a_callback_is_a_harmless_no_op():
    tracker = LibraryScanProgress(None)

    tracker.folder_visited()
    tracker.start_processing({'/a': 1})
    tracker.finish('/a')

    assert tracker.completed == 1


def test_a_failing_callback_never_breaks_the_scan():
    def explode(*_args, **_kwargs):
        raise RuntimeError('boom')

    tracker = LibraryScanProgress(explode)

    tracker.folder_visited()
    tracker.start_processing({'/a': 1})
    tracker.finish('/a')

    assert tracker.completed == 1


def test_reporter_writes_immediately_on_phase_change_and_throttles_within_a_phase():
    clock = FakeClock()
    written = []
    reporter = ThrottledStageReporter(written.append, interval=2.0, clock=clock)

    reporter('discover', count=1)      # 첫 기록
    clock.advance(0.5)
    reporter('discover', count=2)      # 0.5초 - 기록 안 함
    clock.advance(1.6)
    reporter('discover', count=3)      # 마지막 기록 후 2.1초 - 기록
    reporter('process', completed=0, total=10, current='')  # 단계 전환 - 즉시 기록

    assert written == [
        '폴더 탐색 중 · 1개 방문',
        '폴더 탐색 중 · 3개 방문',
        '도서 파일 0/10 (0%) · 남음 10권',
    ]


def test_reporter_always_writes_the_completed_state_and_never_repeats_a_text():
    clock = FakeClock()
    written = []
    reporter = ThrottledStageReporter(written.append, interval=60.0, clock=clock)

    reporter('process', completed=0, total=3, current='')
    reporter('process', completed=1, total=3, current='a')   # 간격 이내 - 기록 안 함
    reporter('process', completed=3, total=3, current='c')   # 완료 - 즉시 기록
    reporter('process', completed=3, total=3, current='c')   # 같은 문구 - 다시 쓰지 않음

    assert written == [
        '도서 파일 0/3 (0%) · 남음 3권',
        '도서 파일 3/3 (100%) · 남음 0권 · DB 반영 중',
    ]


def test_reporter_reset_lets_a_retried_scan_report_from_zero_again():
    """재시도한 스캔은 0부터 다시 시작한다 - 이전 시도의 최고 진행값이 표시를 막으면 안 된다."""
    clock = FakeClock()
    written = []
    reporter = ThrottledStageReporter(written.append, interval=2.0, clock=clock)

    reporter('process', completed=500, total=1000, current='a')
    clock.advance(0.1)
    reporter('process', completed=10, total=1000, current='b')  # reset 없이는 간격 이내라 기록 안 됨
    assert len(written) == 1

    reporter.reset()  # 스케줄러가 재시도 직전에 호출
    reporter('process', completed=10, total=1000, current='b')

    assert written[-1] == '도서 파일 10/1,000 (1%) · 남음 990권 · b'


def test_reporter_survives_a_failing_stage_writer_and_retries_later():
    clock = FakeClock()
    attempts = []

    def flaky(text):
        attempts.append(text)
        if len(attempts) == 1:
            raise RuntimeError('db locked')

    reporter = ThrottledStageReporter(flaky, interval=2.0, clock=clock)

    reporter('discover', count=1)  # 쓰기 실패 - 예외가 밖으로 나가지 않는다
    reporter('discover', count=1)  # 실패했으니 같은 문구라도 다시 시도한다

    assert attempts == ['폴더 탐색 중 · 1개 방문', '폴더 탐색 중 · 1개 방문']
