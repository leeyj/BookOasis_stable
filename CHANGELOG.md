# CHANGELOG
## v3.2.1
- (feat) e-paper 여러 기기 지원: 변환 프로필 6개(`v1`, `x4`, `x3`, `gray-low`, `gray-hd`, `color-hd`), 고해상도 등급은 그림을 회색·컬러 JPEG로 | e-paper multi-device: 6 conversion profiles (`v1`, `x4`, `x3`, `gray-low`, `gray-hd`, `color-hd`); high-res grades use gray/color JPEG images
- (feat) 내 설정에 "웹 받기 기기"·"피드 기기" 선택. 피드·표지·업로드는 피드 기기를 따르고, 설정하지 않으면 지금과 같은 `v1` | "Web download device" and "Feed device" in My settings; the feed, covers and uploads follow the feed device, unchanged `v1` when not set
- (feat) 책 메뉴 "기기용 받기": 웹 받기 기기에 맞춘 EPUB을 받음(Kindle은 Send to Kindle용). 다운로드 버튼은 그대로 원본 | Book menu "Download for device": an EPUB fitted to your web download device (Kindle via Send to Kindle); the download button still gives the original
- (feat) MCP 도구 `epaper_devices`, `set_epaper_device` | MCP tools `epaper_devices`, `set_epaper_device`
- (change) "기타 기기" 항목 이름에 예시 기기(크레마·리디페이퍼·Boox·교보 sam·루나 등) 표시 | "Other device" entries now name example devices (Crema, RIDIPAPER, Boox, Kyobo sam, Luna, etc.)
- (feat) 기기용 받기: 기기 폰트에서 □로 보일 글자 수·견본과 덜 빠지는 폰트를 안내 (BookOasis 펌웨어 기기, 실제 폰트 범위 기준) | Download for device: shows how many characters will appear as □ in the device font, with samples and fonts that miss fewer (BookOasis firmware devices, based on the real font range)
- (change) 펌웨어 기기 EPUB·TXT 변환에서 줄을 뒤집는 RLM류와 한자 이체자 선택자(IVS)를 지움 | Firmware-device EPUB and TXT conversion removes line-flipping RLM-type marks and CJK variation selectors (IVS)
- (change) TXT 변환은 기기와 상관없이 늘 `v1` 한 벌 | TXT conversion is always the single `v1` copy, whatever the device
- (change) MCP `epaper_cache_status`: `profile`·`books` 대신 `default_profile`, 프로필별 `profiles`, `epub_files`·`cover_files` | MCP `epaper_cache_status`: `default_profile`, per-profile `profiles`, `epub_files`/`cover_files` replace `profile`/`books`
- (docs) 기기 추가 기여 가이드 `docs/epaper-devices.md`, 명세 `docs/device-api.md` 갱신 | contributor guide for devices `docs/epaper-devices.md`, updated spec `docs/device-api.md`

## v3.2.0
- (feat) e-paper 리더 전용 OPDS 피드 `/opds-epaper/v1` — EPUB/TXT만, 40개씩 페이지 나눔, 받으면 기기에 맞춘 변환본(그림 2색 디더링, CSS·폰트 정리, TXT는 EPUB으로)을 보냄. 표준 `/opds`는 그대로 원본 | e-paper reader OPDS feed `/opds-epaper/v1` — EPUB/TXT only, 40 per page, downloads are device-optimized copies (2-color dithered images, trimmed CSS/fonts, TXT as EPUB); the standard `/opds` still serves originals
- (feat) KOReader 동기화: 같은 EPUB의 원본과 변환본 중 더 최근 위치를 서로 이어 받음 | KOReader sync: the original and the converted copy of the same EPUB now share the latest position
- (feat) 로컬 EPUB 업로드·변환 API와 기기 API 명세 `docs/device-api.md`, 캐시 관리 MCP 도구(`epaper_cache_status`, `clear_epaper_cache`) | local EPUB upload/convert API, device API spec `docs/device-api.md`, cache MCP tools (`epaper_cache_status`, `clear_epaper_cache`)

## v3.1.7
- (fix) OPDS 시리즈 이름에 `%` 뒤로 영문·숫자가 붙으면(예: `100%AB`) 시리즈를 열어도 책 목록이 비던 문제 수정 | fix OPDS series feeds coming up empty when the series name has `%` followed by letters or digits (e.g. `100%AB`)
- (fix) MariaDB DB 이름 접두사(`MARIADB_DATABASE_PREFIX`)를 바꾼 설치에서 시작 시 컬럼·인덱스 보강이 기본 이름(`media_*`) DB에 적용되던 문제 수정 | fix MariaDB installs with a custom `MARIADB_DATABASE_PREFIX` having startup column/index fixes applied to the default `media_*` databases instead

## v3.1.6
- (fix) TXT/EPUB 두 쪽 보기에서 화면 폭에 따라 왼쪽 쪽 글자가 넘길수록 조금씩 잘리던 문제 수정 | fix the left page's text getting cut off a little more with each page turn in TXT/EPUB two-page view on some screen widths

## v3.1.5
- (fix) TXT/EPUB 페이지 모드에서 글꼴이 적용된 뒤 문단이 겹쳐 보이던 문제 수정 | fix paragraphs appearing on top of each other in TXT/EPUB page mode after the font is applied


## v3.1.4
- (fix) 메타데이터 검색 결과에서 표지를 못 불러오면 대체 표지가 나오지 않던 문제 수정 | fix the fallback cover not showing when a metadata search result's cover fails to load
- (fix) 플러그인 위젯·검색 설명의 링크/강조가 닫히지 않아 뒤 내용까지 링크가 되던 문제 수정 | fix links/emphasis in plugin widgets and search descriptions never closing, turning the rest of the text into a link
- (fix) 휴지통 화면을 연 뒤 카테고리 삭제 등 다른 작업의 로딩 화면이 휴지통 안내로 바뀌던 문제 수정 | fix other tasks (e.g. deleting a category) showing the trash loading overlay after the trash tab was opened
- (fix) 설정 > 단축키의 기본값 표시가 실제 뷰어 동작과 다르던 문제 수정 | fix the shortcut settings showing default keys that differ from what the viewer actually uses
- (security) 알림 토스트와 플러그인 메뉴 이름이 HTML로 해석되던 문제 수정 — 이제 글자 그대로 표시 | toast messages and plugin menu labels are now shown as plain text instead of being parsed as HTML
- (improvement) 영상 강좌가 wmv·flv 파일도 인식(브라우저가 못 여는 형식은 기존처럼 자동 변환 재생), 오디오북 폴더 표지에 bmp·gif 허용 — 확장자 목록을 한 곳으로 통일 | video courses now pick up wmv and flv files (formats browsers can't open are transcoded as before), audiobook folder covers accept bmp and gif — extension lists unified in one place
- (fix) 스캔 중 DB가 잠겨 저장을 다시 시도할 때 그때까지의 기록이 조용히 사라질 수 있던 문제 수정 | fix scan writes that could be silently lost when saving was retried after a database lock
- (fix) 지연 스캔이 DB 저장 실패를 '표지 없음'으로 처리해 7일간 다시 시도하지 않던 문제, 영상 길이 채우기가 오류 한 번에 멈추던 문제 수정 | fix the lazy scan treating a failed DB save as 'no cover' (no retry for 7 days), and the video duration backfill stopping at the first error
- (fix) 앱 OPDS(Tachiyomi 등)의 읽기 진행률이 로그인한 사용자가 아니라 관리자 계정에 저장되던 문제 수정 — 이전 진행률은 관리자 계정에 남아 있음 | fix app OPDS (Tachiyomi etc.) reading progress being saved to the admin account instead of the signed-in user — earlier progress stays on the admin account
- (improvement) API 오류가 서버 로그에 `[API-ERROR]`로 남음(예전엔 대부분 기록 없이 사라짐), MariaDB 잠금 대기·데드락도 스캔 재시도 대상 | API errors are now logged as `[API-ERROR]` (most used to vanish without a trace); MariaDB lock waits and deadlocks now trigger a scan retry
- (refactor) MariaDB 스키마를 `services/schema_mariadb.py`로 옮겨 웹 서버가 CLI 도구를 불러오지 않게 함 | moved the MariaDB schema to `services/schema_mariadb.py` so the web server no longer imports a CLI tool
- (refactor) 쓰이지 않던 레거시 파서 `tools/scanner/parser.py` 제거 — 파서는 `tools/scanner/metadata/` 사용 | removed the unused legacy parser `tools/scanner/parser.py` — use `tools/scanner/metadata/`
- (refactor) 중복 코드 정리 — HTML 이스케이프·플러그인 메뉴·스캐너 DB 기록·표지 파일 이름 규칙 통합, 불필요한 CSS !important 49개와 쓰이지 않던 뷰어 여백 패널 제거 | code cleanup — shared HTML escaping, plugin menu rendering, scanner DB writer and cover file naming; removed 49 redundant CSS !important and an unused viewer margin panel

## v3.1.3
- (feat) 관리자 테이블 뷰 — 책 목록을 표로 보고(정렬·빈 값 필터·컬럼 선택) 셀에서 메타데이터를 바로 수정, CSV 내보내기 (일반/성인 도서, 넓은 화면) | admin table view — see the book list as a table (sort, empty-value filter, column picker), edit metadata in cells, export CSV (general/adult books, wide screens)
- (feat) MCP 도구 `list_series_table` 추가 | add the MCP tool `list_series_table`
- (fix) MCP `update_book_metadata`로 한 필드만 고쳐도 비어 있던 작가·출판사·줄거리에 화면용 문구('-' 등)가 저장되던 문제 수정 | fix MCP `update_book_metadata` writing display placeholders ('-' etc.) into empty author, publisher and summary when changing another field
- (improvement) 시리즈 상세 배경에 표지 대표 색 두 가지로 은은한 그라데이션 — 라이트 테마는 더 옅게, e-paper 테마와 무채색 표지는 적용 안 함 | series detail background gets a subtle two-tone gradient from the cover's main colors — lighter on the light theme, off on the e-paper theme and for colorless covers
- (fix) 시리즈 메타 수정(상세 화면·테이블 뷰·MCP)이 다른 카테고리의 같은 이름 시리즈까지 바꾸던 문제 수정 — 이제 그 카테고리만 바뀌고, 카테고리를 모르는데 이름이 여러 곳에 있으면 고치지 않음 | fix series metadata edits (series page, table view, MCP) also changing a same-named series in another category — now only that category changes, and an ambiguous name with no category is refused
- (improvement) 테이블 뷰에 수정 방법 안내 추가 — 셀을 고치면 잠기고 잠긴 시리즈엔 kavita.yaml이 반영되지 않음, 많은 양은 kavita.yaml + 스캔 권장. CSV는 확인용으로 표시 | table view now explains how to edit — editing locks the series and a locked series ignores kavita.yaml; use kavita.yaml + scan for bulk changes. CSV marked as review-only

## v3.1.2
- (fix) 볼 수 있는 카테고리가 하나도 없는 사용자에게 오디오북·영상 강좌 탭이 빈 채로 보이던 문제 수정 | fix the audiobook and video course tabs showing empty for users with no accessible category
- (fix) 카테고리 권한 확인 중 DB 오류가 나면 접근을 허용하던 문제 수정 — 이제 거부 | fix category permission checks allowing access when the DB check failed — now denied
- (improvement) 영상 강좌 폴더를 옮기거나 이름을 바꾸면 같은 강좌로 인식(이어 보기 기록 유지), 사라진 강좌는 목록에서 숨김 — 오디오북과 같은 규칙 | video courses keep their identity (and watch history) when their folder is moved or renamed, and vanished courses are hidden — same rules as audiobooks
- (improvement) 사용자 추가가 4개 DB에 같은 id로 저장되고, 중간에 실패하면 모두 되돌림 | adding a user now stores the same id in all four DBs and rolls back everywhere if one fails
- (fix) 대시보드 "읽는 중" 카드의 예비 열기 경로가 없는 함수를 불러 아무 일도 하지 않던 문제 수정 | fix the fallback open path of the dashboard "currently reading" card calling a missing function and doing nothing
- (feat) 독서메이트 샘플 플러그인 1.1.0 — 3D 캐릭터(VRM) 옵션 추가(기본 꺼짐, 기본 모델은 pixiv 공식 샘플), 책을 읽는 동안 마스코트 숨김 | Reading Mate sample plugin 1.1.0 — optional 3D character (VRM, off by default, pixiv's official sample model by default); the mascot hides while reading
## v3.1.1
- (fix) 관리자가 영상 강좌 접근을 꺼 둔 사용자에게도 영상 강좌 메뉴가 보이던 문제 수정 — 로그인 때 이 권한 값을 읽지 않고 늘 허용으로 처리했음 | fix the video course menu showing for users whose video access was turned off — the value was not read at sign-in and always treated as allowed
- (fix) 권한 관리의 오디오북·영상 강좌 탭에 메뉴 전체 허용 스위치 추가 — 이 값이 꺼져 있으면 카테고리 권한을 줘도 메뉴가 안 보이는데 화면에서 바꿀 방법이 없었음 | add a menu access switch to the audiobook and video course tabs of permission management — when it was off the menu stayed hidden despite category permissions, and there was no way to change it on screen
- (fix) 권한 관리의 사용자 권한 변경(성인·다운로드·콘텐츠 등급·오디오북)이 영상 DB에는 저장되지 않던 문제 수정 | fix user permission changes (adult, download, content rating, audiobook) not being saved to the video DB
