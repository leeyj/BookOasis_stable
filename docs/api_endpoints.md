# BookOasis API 엔드포인트 명세서

## admin.py
### `[POST]` `/api/media/libraries/add`
- **기능**: 신규 라이브러리 카테고리 추가 및 즉시 스캔
- **함수명**: `add_media_library`

### `[POST]` `/api/media/libraries/edit`
- **기능**: 라이브러리 카테고리 정보 수정 및 재스캔
- **함수명**: `edit_media_library`

### `[POST]` `/api/media/libraries/delete`
- **기능**: 라이브러리 카테고리 및 도서 연쇄 삭제
- **함수명**: `delete_media_library`

### `[POST]` `/api/media/books/<int:book_id>/scan`
- **기능**: 특정 개별 도서 즉시 부분 재스캔 실행
- **함수명**: `scan_single_book_api`

### `[GET]` `/api/media/libraries/schedules`
- **기능**: 모든 카테고리의 스케줄 및 상태 목록 조회
- **함수명**: `get_libraries_schedules`

### `[POST]` `/api/media/libraries/<int:library_id>/scan`
- **기능**: 지정된 라이브러리 카테고리 즉시 비동기 스캔 실행
- **함수명**: `trigger_library_scan`

### `[POST]` `/api/media/libraries/<int:library_id>/cancel-scan`
- **기능**: 지정된 라이브러리 카테고리의 진행 중인 스캔을 중단하도록 플래그 갱신
- **함수명**: `cancel_library_scan`

### `[POST]` `/api/media/libraries/<int:library_id>/scan-covers`
- **기능**: 지정된 라이브러리 카테고리 표지 전용 즉시 비동기 스캔 실행
- **함수명**: `trigger_library_cover_scan`

### `[POST]` `/api/media/libraries/<int:library_id>/schedule`
- **기능**: 지정된 라이브러리 카테고리의 크론 스케줄 주기 업데이트
- **함수명**: `update_library_schedule`

### `[GET]` `/api/media/settings`
- **기능**: 모든 시스템 설정값 조회
- **함수명**: `get_system_settings`

### `[POST]` `/api/media/settings`
- **기능**: 시스템 설정값 추가 및 업데이트
- **함수명**: `update_system_setting`

### `[GET]` `/api/system/status`
- **기능**: 현재 백그라운드 스캔 상태 및 DB 최적화 튜닝 작업 상태 조회
- **함수명**: `get_system_status`

### `[GET]` `/api/media/libraries/<int:library_id>/reports`
- **기능**: 특정 라이브러리 카테고리의 스캔 에러 리포트 목록 조회
- **함수명**: `get_library_reports`

### `[GET]` `/api/media/libraries/reports/view`
- **기능**: 특정 리포트 파일의 에러 리스트 상세 조회
- **함수명**: `view_report_detail`

### `[POST]` `/api/media/settings/trigger-lazy-scan`
- **기능**: Lazy 표지 스캔 강제 즉시 실행 API
- **함수명**: `trigger_lazy_scan_api`

## auth.py
### `[GET, POST]` `/login`
- **기능**: 설명 없음
- **함수명**: `login`

### `[GET]` `/logout`
- **기능**: 설명 없음
- **함수명**: `logout`

### `[POST]` `/change-password`
- **기능**: 설명 없음
- **함수명**: `change_password`

### `[GET]` `/api/admin/users`
- **기능**: 설명 없음
- **함수명**: `get_users`

### `[POST]` `/api/admin/users`
- **기능**: 설명 없음
- **함수명**: `add_user`

### `[DELETE]` `/api/admin/users/<int:target_user_id>`
- **기능**: 설명 없음
- **함수명**: `delete_user`

## library.py
### `[GET]` `/api/media/libraries`
- **기능**: 라이브러리 카테고리 목록 조회
- **함수명**: `get_media_libraries`

### `[GET]` `/api/media/list`
- **기능**: 도서 보관함 시리즈 목록 조회 (무한 스크롤 페이지네이션 + 서버 검색)
- **함수명**: `get_media_list`

### `[GET]` `/api/media/all-list`
- **기능**: Kavita 방식의 선로드를 위해 특정 라이브러리의 전체 시리즈 목록을 페이징 없이 경량 조회
- **함수명**: `get_media_all_list`

### `[GET]` `/api/media/detail`
- **기능**: 특정 시리즈 상세 정보 및 단행본 목록 조회
- **함수명**: `get_media_detail`

### `[POST]` `/api/media/detail/edit`
- **기능**: 시리즈 메타정보 수동 수정 및 표지 업로드
- **함수명**: `edit_media_detail`

### `[GET]` `/api/media/history`
- **기능**: 최근 읽은 도서 히스토리 (최대 20건)
- **함수명**: `get_media_history`

### `[GET]` `/api/media/recently-added`
- **기능**: 신규 추가 도서 (최대 20건)
- **함수명**: `get_media_recently_added`

### `[GET]` `/api/media/meta/recommend`
- **기능**: 상세 설명이 비어있을 때, 유사한 시리즈 이름을 가진 메타데이터 추천
- **함수명**: `get_media_meta_recommend`

### `[POST]` `/api/media/meta/copy`
- **기능**: 추천받은 메타데이터(저자, 출판사, 줄거리 등)를 지정 도서 시리즈에 수동으로 복사 복원
- **함수명**: `copy_media_metadata`

### `[GET]` `/api/media/next-book`
- **기능**: 시리즈 내 다음 도서 권 정보 조회 API
- **함수명**: `get_next_book_api`

### `[POST, PATCH]` `/api/media/books/<int:book_id>/favorite`
- **기능**: 특정 도서의 즐겨찾기 상태 변경
- **함수명**: `toggle_book_favorite`

### `[POST, PATCH]` `/api/media/series/favorite`
- **기능**: 특정 시리즈 전체의 즐겨찾기 상태 변경
- **함수명**: `toggle_series_favorite_api`

### `[GET]` `/api/media/metadata/plugins`
- **기능**: 수동 검색 모달에 사용 가능한 메타데이터 플러그인 목록 조회
- **함수명**: `get_metadata_plugins_api`

### `[GET]` `/api/media/books/search-metadata`
- **기능**: 지정된 메타데이터 플러그인을 활용하여 도서 메타데이터 후보군 검색
- **함수명**: `search_book_metadata_api`

### `[POST]` `/api/media/books/<int:book_id>/apply-metadata`
- **기능**: 사용자가 선택한 메타데이터 정보를 도서 정보에 최종 반영
- **함수명**: `apply_book_metadata_api`

### `[POST]` `/api/media/metadata/plugins/toggle`
- **기능**: 특정 플러그인의 ON/OFF 활성화 상태를 업데이트합니다.
- **함수명**: `toggle_metadata_plugin_api`

### `[POST]` `/api/media/metadata/plugins/save-config`
- **기능**: 특정 플러그인의 JSON 설정 데이터를 DB에 저장합니다.
- **함수명**: `save_metadata_plugin_config_api`

### `[GET]` `/api/media/metadata/plugins/aladin/new-releases`
- **기능**: 알라딘 플러그인을 통해 최신 신간 도서 목록을 반환합니다.
- **함수명**: `get_aladin_new_releases_api`

## stream.py
### `[GET]` `/api/media/stream`
- **기능**: 만화책 ZIP/CBZ 실시간 이미지 추출 및 EPUB 스트리밍 (RAM 캐시 + Prefetch 적용)
- **함수명**: `stream_comic_page`

### `[POST]` `/api/media/progress`
- **기능**: 도서 열람 진행률 저장 및 캐시 정리
- **함수명**: `record_progress_api`

### `[POST]` `/api/media/preload-next-book`
- **기능**: 다음 권 도서 백그라운드 선제 다운로드 및 캐싱 (Web UI 및 타치요미 연동)
- **함수명**: `preload_next_book_api`

## opds.py
### `[GET]` `/opds`
- **기능**: 일반 OPDS 최상위 피드
- **함수명**: `opds_root`

### `[GET]` `/opds-adult`
- **기능**: 성인 전용 OPDS 최상위 피드
- **함수명**: `opds_adult_root`

### `[GET]` `/opds/library/<int:lib_id>`
- **기능**: 설명 없음
- **함수명**: `opds_library`

### `[GET]` `/opds/adult/library/<int:lib_id>`
- **기능**: 설명 없음
- **함수명**: `opds_adult_library`

### `[GET]` `/opds/series/<int:lib_id>/<string:series_name>`
- **기능**: 설명 없음
- **함수명**: `opds_series_books`

### `[GET]` `/opds/adult/series/<int:lib_id>/<string:series_name>`
- **기능**: 설명 없음
- **함수명**: `opds_adult_series_books`

### `[GET]` `/opds/recently-added`
- **기능**: 신규 추가 도서 목록 (일반)
- **함수명**: `opds_recently_added`

### `[GET]` `/opds/recently-read`
- **기능**: 최근 읽은 도서 목록 (일반)
- **함수명**: `opds_recently_read`

### `[GET]` `/opds/adult/recently-added`
- **기능**: 신규 추가 도서 목록 (성인)
- **함수명**: `opds_adult_recently_added`

### `[GET]` `/opds/adult/recently-read`
- **기능**: 최근 읽은 도서 목록 (성인)
- **함수명**: `opds_adult_recently_read`

### `[GET]` `/opds/download/<string:db_type>/<int:book_id>`
- **기능**: 외부 뷰어 앱이 직접 파일을 다운로드하는 엔드포인트
- **함수명**: `opds_download_book`

## stream.py
### `[GET]` `/api/media/stream`
- **기능**: 만화책 ZIP/CBZ 실시간 이미지 추출 (RAM 캐시 + Prefetch 적용)
- **함수명**: `stream_comic_page`

### `[GET]` `/api/media/txt`
- **기능**: 소설·TXT 파일 UTF-8 서빙 (CP949/EUC-KR 자동 변환)
- **함수명**: `get_txt_content`

### `[GET]` `/api/media/pdf`
- **기능**: 대용량 PDF HTTP Range Requests 지원
- **함수명**: `get_pdf_range`

### `[GET]` `/covers/<path:filename>`
- **기능**: 복원된 정적 표지 이미지 서빙 (더블 인코딩 방어용 unquote 적용, 하위 디렉토리 지원)
- **함수명**: `get_cover_image`

### `[GET]` `/api/media/cache/stats`
- **기능**: RAM 캐시 사용량 모니터링
- **함수명**: `cache_stats`

### `[GET]` `/api/media/fonts`
- **기능**: 사용자 정의 폰트 디렉터리 스캔 및 목록 조회
- **함수명**: `list_custom_fonts`

### `[POST]` `/api/media/progress`
- **기능**: 만화, TXT, EPUB, PDF 공통 독서 진행률 API 기록 엔드포인트
- **함수명**: `save_viewer_progress`

### `[POST]` `/api/media/preload-next-book`
- **기능**: 다음 권 도서 백그라운드 선제 다운로드 및 캐싱 API
- **함수명**: `preload_next_book_api`

