# 구글 드라이브 공유 링크 등록 — 서버사이드 복사 전환 계획서 (검증 완료, 구현 전)

## 1. 배경

`gdrive:// 공유 링크로 카테고리 등록`(2026-08-19 구현, 현재 `.env`의 `DEVELOP=true`일 때만 UI 노출)은 남이 공유한 폴더를 Drive REST API로 직접 스트리밍/다운로드해서 서빙한다. 동작은 하지만, kavita.yaml 임베드 커버가 없는 파일은 뷰어/커버 스캔 시마다 압축파일 전체를 서버가 대신 내려받아야 해서 느리다 — 단일 커넥션 HTTP GET이라 rclone 같은 청크 병렬 전송/캐싱이 없다.

이 문제를 우회하는 아이디어: 뷰어가 매번 파일을 받는 대신, **등록 시점에 딱 한 번** 구글 데이터센터 내부에서 사용자 자신의 드라이브로 서버사이드 복사를 해두면, 그 이후로는 이미 검증된(majority userbase가 쓰는) rclone 마운트 기반 스캔/뷰어 경로를 그대로 재사용할 수 있다 — kavita.yaml 읽기, ComicInfo 파싱, ZIP 오프셋 부분 스트리밍이 전부 "공짜로" 다시 동작한다.

관련 기존 문서: `docs/share_google_drive.md` (BookOasis 서버간 공유용으로 설계된 문서지만, 핵심 rclone 서버사이드 복사 메커니즘은 여기에도 그대로 재사용 가능 — 중계서버/메시지큐 부분은 이 기능엔 불필요).

## 2. 실현 가능성 검증 (2026-08-19, 완료)

### 2.1 1차 시도: `rclone copy --drive-server-side-across-configs` — 실패

사용자의 실제 홈 서버(rclone v1.75.0)에 붙어 라이브 테스트:

```bash
rclone lsf "GDS:,root_folder_id=<외부공유폴더ID>:" -vv
# → ERROR: error listing: directory not found
```

- `GDS` 리모트(SJVA 커뮤니티 OAuth 중계, `scope=drive.readonly`)와 `sjva` 리모트(개인 드라이브, `scope=drive`, 쓰기 권한 있음) **둘 다 동일하게 실패**.
- 즉 원인은 OAuth 스코프(읽기전용) 문제가 아니라, **rclone이 `root_folder_id`로 "본인 소유가 아니고 한 번도 내 드라이브에 추가(Add to My Drive)된 적 없는" 폴더를 다루는 방식 자체의 한계**. 로그상 rclone이 이를 "공유 드라이브(Shared Drive)" 루트로 오인해서 엉뚱한 ID(`0AGVKjNyUMukRUk9PVA`)를 찾고 있었음.
- 반면 BookOasis 자체의 `GDRIVE_API_KEY` 기반 `files.list` 조회는 동일한 폴더를 문제없이 읽는다 — API 키 기반 익명 조회와 rclone 백엔드의 내부 폴더 순회 로직이 서로 다른 제약을 갖는다.

### 2.2 2차 시도: rclone 우회 + Drive REST API `files.copy` 직접 호출 — **성공**

rclone의 폴더 탐색을 아예 거치지 않고, `rclone.conf`에 이미 저장돼 있는 사용자 계정의 OAuth 자격증명(client_id/client_secret/refresh_token, 전용 스코프 `drive`)으로 access token을 새로 발급받아 Drive REST API를 직접 호출:

**검증 방법** (전체 스크립트는 세션 스크래치패드에서 실행 후 폐기, 아래는 핵심 로직 요약):
```python
# 1) rclone.conf에서 refresh_token/client_id/client_secret 추출 (원격 서버에서만, 토큰 자체는 로그에 출력 안 함)
dump = json.loads(subprocess.check_output(["rclone", "config", "dump"]))
cfg = dump["sjva"]  # 개인 드라이브 리모트 (scope=drive)

# 2) OAuth2 표준 리프레시 플로우로 access_token 신규 발급
POST https://oauth2.googleapis.com/token
  client_id, client_secret, refresh_token, grant_type=refresh_token

# 3) 목적지 폴더 생성 (Drive REST API, 내 드라이브 안)
POST https://www.googleapis.com/drive/v3/files
  {"name": "...", "mimeType": "application/vnd.google-apps.folder", "parents": ["root"]}

# 4) 서버사이드 복사 — 소스는 "내가 소유하지 않지만 공유돼서 읽기 권한이 있는" 파일
POST https://www.googleapis.com/drive/v3/files/{source_file_id}/copy
  {"parents": [목적지_폴더_id]}
```

**결과**: 성공. 실제 공유 폴더의 kavita.yaml(16MB, 남이 소유한 파일)을 사용자 본인 드라이브로 복사 → **복사 직후 `rclone lsf sjva:...`로 즉시 조회됨** (별도 VFS 갱신 없이 바로 보임, `docs/share_google_drive.md`가 이미 지적했듯 필요시 `/vfs/refresh` 트리거로 캐시 갱신 가능). 테스트 아티팩트(복사된 파일 + 임시 폴더)는 검증 직후 API로 삭제해 정리 완료.

**핵심 결론**: 소스 파일 ID 조회는 기존에 이미 동작하는 `GDRIVE_API_KEY` 기반 리스팅을 그대로 쓰고, 복사만 rclone.conf의 OAuth 토큰으로 Drive REST API를 직접 호출하면 두 블로커(폴더 해석 실패, 스코프 문제) 모두 우회된다.

## 3. 왜 지금 바로 구현하지 않는가

이 전환은 "위에 얹는 최적화"가 아니라 **읽기 경로의 근간을 바꾸는 일**이다:
- 사용자의 OAuth 자격증명을 다루게 됨 (rclone.conf에서 refresh_token을 읽어 우리 쪽 코드로 API를 호출) — 보안/권한 범위를 신중히 설계해야 함.
- 등록 UX가 완전히 달라짐 (즉시 등록 → 즉시 스캔이 아니라, 복사 요청 → 비동기 완료 대기 → 완료 후 스캔).
- rclone이 설정 안 된 사용자를 위한 폴백(오늘 만든 직접 다운로드 방식)도 계속 유지해야 함 — 두 경로 공존.
- 실패/부분실패(복사 도중 오류, 용량 초과, 권한 회수 등) 처리 설계가 필요.

그래서 서두르지 않고 아래 단계로 나눠 차근차근 구현하기로 함.

## 4. 구현 단계 (초안, 순서대로 — 각 단계마다 검증 후 다음 단계로)

1. **자격증명 접근 계층**: rclone.conf에서 지정된 리모트의 client_id/client_secret/refresh_token을 안전하게 읽어와 access_token을 발급/캐싱하는 유틸 (`utils/` 하위 신규 모듈). 토큰은 절대 로그에 남기지 않음.
2. **단일 파일 서버사이드 복사 함수**: file_id + 목적지 폴더 경로를 받아 `files.copy`를 호출하는 최소 단위 함수 + 재시도/에러 처리.
3. **폴더 단위 복사 오케스트레이션**: 기존 `fetch_gdrive_folder_files()` 결과(폴더 구조 + file_id 목록)를 순회하며 목적지 폴더 트리를 만들고 각 파일을 복사. 진행률 추적(몇 개 중 몇 개 완료) 필요.
4. **완료 감지 + 스캔 트리거**: 복사가 비동기(수십 초~수 분)일 수 있으므로 완료 판정 로직(폴링 또는 콜백) → 완료되면 해당 카테고리에 대해 기존 `process_folder_task` 스캔을 트리거.
5. **UX (2.1 설계)**: 별도 모달 — 링크 입력 → 감지된 폴더 체크박스 목록 → 선택 → 복사 시작 → 완료 알림 → 자동 스캔. (오늘 숨긴 인라인 gdrive 카테고리 타입 버튼은 이 새 모달로 대체될 예정.)
6. **폴백 유지**: rclone 미설정 사용자를 위해 기존 직접 다운로드(`utils/drive_helper.py::resolve_gdrive_local_path`) 경로는 그대로 남겨두고, 서버사이드 복사가 가능한 조건(설정된 rclone remote + write scope 확인됨)일 때만 새 경로를 우선 사용.

## 5. 미해결 질문

- 사용자가 여러 rclone 리모트를 갖고 있을 때(오늘 예시처럼 `sjva`, `GDS` 등) 어떤 리모트를 "내 드라이브(쓰기 대상)"로 쓸지 어떻게 지정받을 것인가 — 카테고리 설정에 필드 추가? 자동 감지(scope=drive인 것 우선)?
- 복사량이 매우 클 때(TB 단위) Drive의 일일 API 쿼터/속도 제한에 걸릴 가능성 — 배치/재시도 정책 필요.
- 복사 완료 후 원본 소스가 삭제되거나 공유가 해제되면 이미 복사된 사본은 안전하게 남는지(그럴 것으로 예상되지만 확인 필요).

## 6. 향후 확장 아이디어 (브레인스토밍, 2026-08-19)

### 6.1 주기적 재동기화(신규 파일 자동 추가 복사)

한 번 복사하고 끝나는 게 아니라, 등록해둔 원본 링크를 계속 기억해뒀다가 주기적으로 새 파일만 추가 복사하는 것도 자연스럽게 이어지는 확장이다.

- 라이브러리 row에 "원본 공유 링크/folder_id"와 "복사 목적지 경로"를 함께 저장해두면, 주기적으로 `fetch_gdrive_folder_files()`로 소스를 다시 조회해서 아직 복사 안 된 file_id만 `files.copy`하면 된다 (이미 저렴하게 동작 확인된 API 키 기반 리스팅 재사용).
- 스케줄러 인프라도 이미 있다 — `[Scheduler] Lazy cover scanner job registered: Schedule=0 3 * * *` 같은 기존 APScheduler cron 패턴을 그대로 재사용.
- **삭제 동기화는 하지 않는 걸 기본값으로 권장**: 원본에서 파일이 빠졌다고 이미 사용자 드라이브에 복사된 사본까지 지우면 예상 못한 데이터 손실이 될 수 있다. "새로 추가된 것만 감지해서 더하기"가 안전하다.
- 트레이드오프: 등록된 gdrive 소스가 많아지면 주기 체크마다 Drive API 호출이 누적되므로, 기존 영상/오디오북 lazy backfill처럼 동시성/간격을 설정 가능하게 해야 한다 (일일 쿼터 고려, §5의 "TB 단위 복사 시 쿼터" 질문과 동일 축).

### 6.2 소스 링크 끊김 감지 및 경고

공유한 사람이 나중에 링크를 차단/삭제하면, 그걸 조용히 실패시키지 말고 사용자에게 알려야 한다.

- 감지: 주기 체크(6.1) 때 소스 조회가 실패하면서 "진짜 빈 폴더"가 아니라 Drive API의 403(권한 없음)/404(존재하지 않음)가 오면, 그 라이브러리에 "소스 끊김" 플래그를 세팅한다.
- UI: 새로 만들 필요 없이, 스캐너가 이미 쓰는 "커버 미검출" 류의 카테고리/도서 단위 인라인 경고 배너 패턴을 그대로 재사용.
- **디바운스 필요**: 일시적 네트워크 오류/타임아웃을 "링크 끊김"으로 오판하면 안 되므로, 연속 N회 실패해야 경고로 격상시켜야 한다 (1회성 오류와 진짜 권한 철회를 구분).
- 링크가 끊겨도 **이미 복사해둔 사본은 그대로 유지**한다 — 6.1의 "삭제 동기화 안 함" 원칙과 일관됨. 끊김 경고는 어디까지나 "앞으로 새 파일이 안 들어온다"는 알림이지, 기존 데이터를 지우는 트리거가 아니다.

## 7. 상태

**아이디어 및 실현 가능성 검증 완료 (2026-08-19).**

**2026-08-21 진행 상황**: §4의 1단계는 별도 모듈로 만들지 않고 2단계 구현에 바로 녹였다. 2단계(rclone.conf 기반 "내 드라이브(쓰기 가능)" 리모트 감지 + 관리자가 리모트/목적지 경로 선택 + 실제 쓰기 권한 검증)까지 구현 완료:
- `utils/rclone_gdrive_copy.py` — `list_writable_drive_remotes()`, `_get_access_token()`, `validate_remote_access()`
- `api/routes/gdrive_copy_routes.py` (`GET /api/gdrive-copy/remotes`, `POST /api/gdrive-copy/validate`, `DEVELOP=true`에서만 노출)
- `libraries` 테이블에 `gdrive_copy_remote`/`gdrive_copy_dest_path` 컬럼 추가 (SQLite/MariaDB 양쪽, 컬럼 자동 백필 포함)
- 기존 gdrive 라이브러리 모달(`library_modal.html`)에 리모트 선택/목적지 경로/"대상 검증" UI 추가

**2단계는 실서버에서 검증 완료** (2026-08-21): 리모트 드롭다운에 실제 rclone 리모트가 떴고, "대상 검증" 클릭 시 실제 Drive에 폴더가 생성되고 계정 이메일이 정상 표시됨.

**2026-08-21 추가 진행**: 사용자 판단으로 "공유 링크 직접 스트리밍"(기존 gdrive 카테고리 타입)과 "복사해오기"를 완전히 분리하기로 결정. 2단계에서 기존 카테고리 추가 모달에 끼워 넣었던 리모트 선택/검증 UI는 제거하고, 별도의 "Drive에서 복사해오기" 모달(사이드바 새 버튼, `DEVELOP=true`+관리자 전용)로 이전. 3단계(실제 폴더 전체 순회 복사 + `scanner_queue`의 `gdrive_copy` task_type + 완료 후 라이브러리 자동 생성/스캔 트리거)까지 구현 완료:
- `utils/rclone_gdrive_copy.py`에 `copy_file()`(files.copy), `resolve_dest_folder()` 추가
- `services/gdrive_copy_service.py` (신규) — `start_gdrive_copy_job()`(큐 등록), `run_gdrive_copy_job()`(소스 폴더 목록 수집 → 목적지 폴더 트리 생성 → 파일별 복사+진행률(stage)+취소 확인 → 완료 시 `CategoryService.add_library()` + `library_scan` 큐 등록)
- `services/scanner_queue.py`에 `gdrive_copy` task_type 배선(`_get_task_key`, 워커 디스패치, `_process_gdrive_copy`)
- `api/routes/gdrive_copy_routes.py`에 `POST /api/gdrive-copy/start` 추가
- `templates/components/modals/gdrive_copy_modal.html` + `static/js/category/gdrive_copy_modal.js` (신규 전용 모달), 사이드바 버튼(`static/js/category/index.js`, `window.DEVELOP_MODE` 게이팅)
- `static/js/scan_activity_status.js`에 `gdrive_copy` 라벨 추가(기존 진행률 위젯 그대로 재사용)

**2026-08-21 재설계**: 실제 모달을 써보니 매번 카테고리 이름/그룹/목적지 경로/로컬 스캔 경로를 입력하는 게 번거롭고, "복사 목적지"라는 개념 자체가 헷갈린다는 게 확인됨. 최종 확정한 전제: **"복사 받을" 로컬 경로는 미리 카테고리로 등록해둔다.**

- "카테고리 추가/수정"(로컬 타입) 모달에 "서버사이드 복사 대상 리모트" + "복사 목적지 경로" + "대상 검증" 필드를 다시 넣음(2단계 UI와 동일한 API, 위치만 gdrive 타입 대신 로컬 타입 쪽으로 이동) — 관리자가 카테고리를 만들 때 "이 로컬 마운트 경로는 이 리모트/목적지에 대응한다"를 한 번 등록해두는 용도.
- "Drive에서 복사해오기" 모달은 이제 **대상 카테고리 선택(드롭다운, `gdrive_copy_remote`가 설정된 카테고리만 노출) + 공유 링크 입력**, 단 두 필드로 단순화. 이름/그룹/리모트/목적지/로컬경로 입력 전부 제거 — 전부 선택한 카테고리에서 자동으로 가져옴.
- `services/gdrive_copy_service.py`: `library_id` 기반으로 재작성 — 새 라이브러리를 생성하지 않고, 선택된 기존 카테고리의 `physical_path`/`gdrive_copy_remote`/`gdrive_copy_dest_path`를 그대로 사용해 복사 후 그 카테고리를 재스캔. task_key도 `gdrive_copy_{db_type}_{library_id}`로 변경(카테고리당 중복 실행 방지, 반복 동기화에 자연스럽게 대응).

**실서버 end-to-end 검증 완료 (2026-08-21)**: 카테고리에 리모트/목적지 경로를 설정 → "Drive에서 복사해오기"에서 그 카테고리 선택 + 공유 링크 입력 → 실제로 지정한 목적지 폴더 안에 정확히 복사되고 로컬 스캔도 정상 확인. (중간에 "한 단계 위로 복사되는" 현상이 있었으나, 코드 버그가 아니라 카테고리의 목적지 경로 필드를 비워둔 사용자 설정 문제였음 — 채워 넣자 바로 정상 동작.)

**알려진 UX 약점**: `physical_path`(로컬)와 `gdrive_copy_dest_path`(Drive 쪽)가 서로 독립된 입력 필드라 관리자가 수동으로 일치시켜야 함 — 둘이 안 맞아도 저장 시점엔 검증되지 않음. 필요시 나중에 "대상 검증" 시 physical_path와의 정합성도 함께 확인하는 개선 여지 있음(요청 전까지 먼저 만들지 않기로 함).

§6(주기 동기화/끊김 감지)은 이 설계와 방향이 잘 맞음 — 같은 카테고리를 다시 선택해 새 링크로 재실행하면 사실상 수동 재동기화가 됨. 자동화는 아직 미착수.
