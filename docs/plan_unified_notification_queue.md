# Plan: 에러 문제 카드 + 종합 알림센터 (스캔 알림 개편 포함)

**상태: 설계 확정, 구현 진행 중 (4단계까지 완료).** 2026-09-29 세션에서 정리·결정. 구현은 **8장 "구현 순서"**를 따른다.

> **새 세션에서 이어받을 때**: ① 이 문서의 "결정:" 소절들이 확정 사항이다(바꾸려면 사용자와 상의).
> ② 8장에서 `✅ 완료`가 안 붙은 가장 앞 단계부터 진행한다. ③ 남은 미정 사항은 맨 아래 목록 참고.

## 진행 현황 (2026-10-02 세션 종료 시점)

| 단계 | 상태 | 검증 |
|---|---|---|
| 0 선행 정리 | ✅ 커밋 `4a91006` | 홈 서버 배포 |
| 1 데이터 기반 (problem 테이블/서비스, SystemHealthService 흡수) | ✅ | 테스트 서버 MariaDB |
| 2 스캔 완료 기록 (`scan_history.result_summary`, `trigger_type`, 90일 정리) | ✅ | 테스트 서버 실제 스캔 |
| 3 알림센터 개편 ("스캔 활동" → "알림", 공통 항목/렌더러, 읽음, NEW 배지 색) | ✅ | 하네스 화면 + 테스트 서버 실데이터 어댑터 |
| 3+ 알림 일괄 지우기 ([지우기] + 토스트 되돌리기) | ✅ 2026-10-02 | 테스트 서버 MariaDB: 일반/관리자 세션 API 흐름 |
| 4 스캐너 문제 기록 + 문제 카드 (삭제 직전 안전장치, 카드 펼침/조치, MCP 조회 도구) | ✅ | 테스트 서버: NAS 마운트 내림/복구, 임시 카테고리 대량 사라짐 |
| 5 진단 버튼 + "관리자에게 알리기" | ✅ 2026-10-02 | 테스트 서버: GDrive 도서 진단, 일반 세션 뷰어 신고 → 카드 → 해결됨 (실제 로그인 화면) |
| 6 플러그인 계약 (`report_problem`/`resolve_problem`) | ✅ 2026-10-02 (사용자 진행 지시) | 테스트 서버: 플러그인 카드 표시·조치 RPC·비활성화 정리 |
| 7 필요해질 때만 | 대기 | |

**작업 트리 상태**
- **전부 미커밋.** 사용자 지시: 구현이 모두 끝날 때까지 커밋하지 않는다.
- 같은 트리에 별개 작업이 섞여 있다 — 워커 교체 멈춤 수정(`gunicorn.conf.py`, `services/scheduler_service.py`, CHANGELOG 해당 줄),
  `docs/plan_tts_audiobook.md`(이 작업과 무관한 수정). 커밋할 때 나눠서 올린다.
- 테스트 서버(192.168.0.21)에는 6단계까지 배포됨. 홈 서버에는 1단계 이후 아무것도 배포 안 함.
- 로컬 테스트: Python 411 통과 / JS 106 통과 (실패 1건 `test_plugin_permissions::test_plugin_permission_accepts_string_library_id`는 작업 전부터 있던 것).

**새로 생긴 주요 파일**
- 서버: `services/problem_service.py`, `services/scan_problem_service.py`, `services/problem_card_service.py`,
  `services/notification_service.py`, `repositories/{sqlite,mariadb}/problem_repository.py`, `api/routes/problem_routes.py`
  5~6단계: `services/book_diagnosis_service.py`, `services/user_problem_report_service.py`, `services/plugin_problem_service.py`
- 화면: `static/js/notification_render.js`(순수 함수), `static/js/notification_cards.js`(카드 펼침/조치), `static/js/scan_activity_status.js`(폴링·DOM)
  5단계: `static/js/book_diagnosis.js` + `diagnosis_render.js`(진단 모달), `static/js/viewer/report_problem.js`(뷰어 오류 자리 버튼)
- 테스트: `tests/test_problem_service.py`, `test_system_health_service.py`, `test_scan_result_summary.py`, `test_notification_service.py`,
  `test_notification_render.mjs`, `test_scan_problem_gate.py`, `test_problem_card_service.py`
  5~6단계: `test_book_diagnosis.py`, `test_plugin_problem_service.py`, `test_book_menu_rules.mjs`(진단 메뉴)

**휴지통 7일 자동 비우기 ✅ 수정 (2026-10-02, 사용자 결정: "동작해야 한다")**: `tools/scanner/sync_detector.handle_deleted_books`가
이미 휴지통에 있는 도서의 `deleted_at`을 유지하도록 변경(비어 있던 예전 행만 지금 시각). 기존 휴지통은 그동안 매 스캔마다
시각이 갱신돼 있었으므로 배포 후 **마지막 스캔 시점 + 7일**에 한꺼번에 비워진다(대량 사라짐 판정은 휴지통 이동 단계라 이 비우기와 무관).
MariaDB SET 평가 순서(왼쪽부터) 때문에 `deleted_at`을 `is_deleted`보다 먼저 둔다 - 테스트 서버 MariaDB 임시 테이블로 확인.

**알림 일괄 지우기 ✅ 완료 (2026-10-02)** — 7장 "결정: 알림 일괄 지우기" 구현 메모 참고.
**5단계 ✅ 완료 (2026-10-02)** — 8장 5단계 구현 메모 참고.
**6단계 ✅ 완료 (2026-10-02)** — 8장 6단계 구현 메모 참고. 1~6단계 구현 끝. 7단계는 필요해질 때만. 남은 일 = 커밋(작업 단위로 나눠서) + 홈 서버 배포.

**남은 자잘한 것 (단계와 별개)**
- 음성 미리 만들기 "최근 완료"가 아직 웹 프로세스 메모리 30분 기준 — 7일 보관하려면 작업 테이블에서 읽도록 변경 필요.
- MCP `propose_rescan`(Tier B 재스캔 제안) 미구현.
- [시리즈 재스캔]이 쓰는 기존 `scan-path` API는 웹 요청 안에서 동기 실행 → GDrive 폴더면 응답이 오래 걸릴 수 있음.
- ~~실제 앱에서 알림 팝오버 확인~~ → 2026-10-02 테스트 서버 로그인 화면(Playwright)에서 팝오버·카드 펼침·[지우기]/되돌리기·진단 모달·뷰어 신고 확인.

## 배경 / 동기
- 2026-09-17 ~ 09-29, 시리즈 요약 테이블(`series_summary`) 재생성이 `created_at`이 NULL인
  도서 **1권** 때문에 매 스캔마다 실패했다. 실패는 로그에만 남아 12일간 아무도 몰랐고,
  그 사이 일반 도서 카테고리 목록이 9/16 상태로 멈춰 새 카테고리가 "등록된 도서가 없습니다"로 보였다.
- 이 사건 후 최소 대책으로 `services/system_health_service.py`(`SystemHealthService.track`)를
  만들었다: 계속 실패 중인 백그라운드 작업을 관리자에게만 상단 스캔 활동 아이콘의 빨간 점 +
  팝오버 한 줄로 보여 주고, 다음 성공 때 자동 해제한다.
- 실제로 띄워 보니 **경고 문구(`(1048, "Column 'latest_added' cannot be null")`)만으로는 무엇이
  문제이고 뭘 해야 하는지 짐작하기 어려웠다.** 또 스캔/음성 생성/시스템 경고가 한 팝오버에
  제각각 섞여 있어, 이를 종합 알림 큐로 정리할 필요가 있다.

## 설계 원칙
1. **책 단위로 기록하고, 원인 단위로 알린다.** 기록은 세밀하게, 알림은 묶어서.
2. **에러 문장이 아니라 "무엇이 / 왜 / 뭘 누르면 되는지"를 보여 준다.**
3. **고칠 수 있는 건 에러로 만들지 않는다.** 자동 복구하고 요약만 남긴다
   (예: `db_migration_service._backfill_books_created_at`).
4. **빨간 점은 "조치 필요"에만 쓴다.** 남발하면 무시하는 습관이 생긴다.
5. **파괴적 조치는 원인 점검을 통과해야만 가능하다.** 마운트 끊김을 "파일 삭제됨"으로
   오판해 대량 휴지통 이동하는 사고를 구조적으로 막는다.

## 1. 문제 카드: 코드 + 대상 + 조치
발생 지점에서 원문 예외 대신 **코드와 대상**을 기록하고, 코드별로 설명 문구와 조치 버튼을
카탈로그로 미리 정의한다.

| 코드 | 사용자 문구 | 조치 |
|---|---|---|
| `file_missing` | 파일이 원래 위치에 없습니다 (이동/삭제) | 재스캔, 휴지통으로 이동 |
| `remote_unavailable` | 원격 드라이브 연결이 끊겼습니다 | 관리자: 마운트 상태 확인 / 일반: 잠시 후 재시도 |
| `file_corrupt` | 파일이 손상되어 열 수 없습니다 | 다시 스캔, 숨기기 |
| `metadata_invalid` | 도서 정보 일부가 비정상입니다 | 자동 복구 |
| (분류 안 됨) | 알 수 없는 오류 | 관리자에게 보고, 원문은 접어서 표시 |

- **대상(book_id / library_id / 경로)은 필수.** 이번 경고의 가장 큰 약점이 "어떤 책인지" 몰랐던 것.
- 분류는 **예외 발생 지점에서 코드를 붙이는 방식**이 주, 메시지 정규식 분류는 보조.
- 문구는 i18n 키로 관리(ko/en).

## 2. 사용자별 노출
- **일반 사용자**: 알림 큐를 볼 일이 없어야 한다. 에러는 **자기가 한 동작 자리에서만**
  (예: 뷰어 열기 실패 → 그 자리에 한 줄 + 버튼 1개).
- **관리자**: 종합 알림 큐에서 묶음 카드로 본다.

### 결정: 알림센터는 하나, 항목별 `audience`로 거른다 (2026-09-29)
도서 관리는 전부 관리자 권한이므로 일반 사용자에게 스캔/문제 카드를 보여 줄 필요는 없다.
다만 "음성 준비됨"처럼 일반 사용자도 받아야 하는 알림이 있어, **화면을 나누지 않고
항목마다 보는 사람을 정한다.**

| 항목 | audience |
|---|---|
| 스캔 진행/완료, 문제 카드, 시스템 경고 | 관리자만 |
| 음성 미리 만들기 (진행 / 완료 "음성 준비됨" / 실패) | 요청한 본인 + 관리자 |

- 서버가 조회 시 로그인 사용자 기준으로 걸러서 내려준다. 렌더러는 권한을 몰라도 된다.
  (음성 미리 만들기는 이미 `services/tts_pregen_service.py` `activity_for(user_id, is_admin, ...)`로
  이렇게 동작한다 — 이 방식을 알림센터 전체 규칙으로 넓힌다.)
- 일반 사용자 아이콘:
  - 본인 항목이 없으면 **흐리게 표시** (숨기지 않는다 — 아이콘이 사라지면 그것대로
    "뭔가 고장났나"로 인식할 수 있으므로).
  - 주황 점(진행 중)은 **본인 음성 생성이 돌 때만**. 관리자 스캔 때문에 가족 계정 아이콘이
    깜빡이지 않게 한다.
  - 빨간 점(조치 필요)은 관리자에게만.
- 따라서 정리되는 것:
  - **읽음 처리**: audience별로 한다. 관리자 항목은 관리자 계정 기준, 음성 준비됨은 요청한 본인 기준.
  - **일반 사용자의 재스캔 요청**: 스캔 항목을 볼 일이 없으므로 요청 기능은 만들지 않는다.
    뷰어 등에서 에러가 났을 때 "관리자에게 알리기" 정도만 남긴다.

## 3. 대량 발생 대응 (핵심)
마운트 끊김 등으로 수만 건이 한꺼번에 발생해도 큐가 폭주하지 않아야 한다.

```
[발생 기록]  대상 1개 x 코드 1개 = 1행 (재발 시 count/last_seen만 증가)
     ↓ 묶기: (코드, 카테고리)
[묶음]       "파일 없음 · <카테고리> · 1,234권"
     ↓ 원인 추정: 짧은 시간 대량 발생 + 루트/마운트 점검 실패
[알림 큐]    카드 1장: "원격 드라이브 연결 끊김 (영향 1,234권)"
```

- 발생 기록은 `(대상, 코드)` UPSERT → 상한이 "대상 수"로 고정되어 폭주하지 않는다.
- 알림 카드에는 **개수 + 예시 3~5건 + 일괄 조치**만. 전체 목록은 카드 클릭 시 페이지네이션 조회.
- **원인 접기**: 같은 카테고리에서 `file_missing`이 몰리면 먼저 카테고리 루트/마운트 생존을 점검하고,
  죽어 있으면 개별 건은 하위로 숨기고 원인 카드 1장만 띄운다. 이 상태에서는 개별 파일 삭제/휴지통
  처리를 하지 않는다. (현재 스캐너에 동등한 방어가 이미 있는지 구현 시 먼저 확인할 것.)

### 결정: 발생 기록은 신규 테이블 (2026-09-29)
기존 테이블(`scan_history`는 작업 단위, `settings`는 키-값)로는 "대상 x 코드" 단위 기록과
알림센터 연계(묶음/해결/음소거)를 담기 어렵다. 향후 확장을 위해 **전용 테이블을 새로 만든다.**

스키마 초안 (이름·컬럼은 구현 시 확정):

```
problem_occurrences
  id                PK
  code              file_missing / remote_unavailable / file_corrupt / metadata_invalid / ...
  severity          action_required / notice / auto_fixed
  source            scanner / system / viewer / plugin:<namespace_id>
  db_type           general / adult / audiobook / video   (도서가 DB별로 나뉘어 있으므로)
  library_id        NULL 가능 (시스템 항목)
  target_type       book / series / library / system
  target_id         book_id / "library_id|series_name" / library_id / 작업 키(예: series_summary:general)
  target_path       파일/폴더 경로 (표시 + 진단용)
  series_key        "library_id|series_name" (book·series 행에 저장, 화면엔 노출 안 함 —
                    도서가 삭제돼도 JOIN 없이 시리즈별로 모으기 + 플러그인 활용용)
  group_key         카드 키 = code|db_type|library_id (예: file_missing|general|80)
  message           원문 예외 (잘라서 저장, 화면엔 접어서 표시)
  context           JSON (추가 정보)
  occurrence_count  재발 횟수
  first_seen_at / last_seen_at
  status            open / resolved / muted
  resolved_at
  UNIQUE (code, db_type, target_type, target_id)   -- 재발은 UPSERT로 count/last_seen만 증가
  INDEX  (status, group_key), (last_seen_at)
```

- 저장 DB: general DB (`scan_history`와 같은 위치). 대상의 DB는 `db_type` 컬럼으로 구분.
- 새 테이블이므로 `docs/change_db_guide.md` 3번 절차대로 `_SCHEMA_SQL`(SQLite)과
  `MARIADB_CENTRAL_SCHEMA`(MariaDB) **둘 다** 추가해야 한다.
- 시각은 `SystemHealthService`에서 겪은 문제(서버 UTC vs 브라우저 KST 9시간 어긋남)를 반복하지 않도록
  타임존 포함 형식으로 다룬다.
- **`SystemHealthService`는 이 테이블로 흡수한다** (`target_type='system'` 행). 그 전까지는 현재
  settings 저장 방식을 유지하고, `track()` 호출부는 그대로 두고 내부 저장소만 교체하는 방향.
- 묶음 단위 상태(음소거 등)는 별도 작은 테이블(`problem_groups`)에 둔다 → 아래 "결정: 묶는 기준" 참고.

### 결정: 묶는 기준 (2026-09-29)
**기록 단위와 표시 단위를 분리한다.** 에러의 주체가 시리즈일 수도, 개별 도서일 수도 있어서
기록할 때 억지로 하나로 정하지 않는다.

1. **기록 = 에러가 실제로 난 단위 그대로.**
   - 파일 하나가 없음/손상 → `book`
   - 시리즈 폴더 자체의 문제(시리즈 커버, kavita.yaml 파싱, 폴더 통째로 없음) → `series`
     (시리즈는 DB 행이 아니므로 `target_id = "library_id|series_name"`)
   - 카테고리 루트/마운트 → `library`, 시스템 작업 → `system`
   - `book`/`series` 행에는 **`series_key`를 함께 저장**한다. 화면에는 노출하지 않지만, 도서 삭제 후에도
     시리즈별 집계가 가능하고 나중에 플러그인에서 활용할 수 있다.
2. **카드 = 문제 종류 x 카테고리** (`group_key = code|db_type|library_id`).
   - 원인 하나로 접는 판단(마운트 점검)도 이 단위에서 한다.
   - 시리즈를 카드 단위로 하면 카드 수가 너무 많아져 채택하지 않음.
3. **카드 안에서는 시리즈별로 위로 접어 올린다.**
   ```
   [빨강] 파일 없음 · 리디(GDS,소설) · 124권          [모두 재스캔] [알고 있음]
      ▸ 원피스 — 110권 전체                          [시리즈 재스캔]
      ▸ 나루토 — 72권 중 12권                        [시리즈 재스캔]
      ▸ 살인 현장은 구름 위 — 1권                    [재스캔] [진단]
   ```
   - 한 시리즈 전 권이 같은 에러면 "N권 전체", 일부면 "M권 중 N권". 펼치면 해당 도서 목록.
   - `series` 단위 에러는 처음부터 시리즈 줄로, 1권짜리는 도서 줄로 나온다.
   - 조치 버튼은 단계별: 카드 [모두 재스캔], 시리즈 [시리즈 재스캔](기존 `api/routes/scan_routes.py`
     시리즈 단위 스캔 등록 재사용), 도서 [재스캔]/[진단].
4. **음소거 등 카드 상태는 `problem_groups` 작은 테이블**(예: `group_key`, `muted_at`, `muted_count` ...).
   행마다 상태를 들고 있으면 "새 대상이 생기면 다시 표시" 판단이 복잡해진다.
   음소거 이후 카드에 새 대상이 추가되면(개수 증가) 다시 표시한다.

### 결정: 대량 발생 기준 (2026-09-29)
1. **범위 = 카테고리** (카드 단위와 동일). **시간 창 = 해당 카테고리 스캔 1회** — 임의의 "N분" 대신
   스캔 종료 시 결과로 판단한다.
2. **신호 기준 = 비율 20% 이상 AND 20건 이상** (한 스캔에서의 `file_missing`).
   - 비율만 쓰면 7권 중 2권(28%)도 대량, 건수만 쓰면 7만 권 카테고리의 200건도 대량이 되므로 둘 다 요구.
   - 카테고리 크기 편차가 크다 (홈 서버 기준 7권 ~ 7만 권).
3. **숫자는 신호일 뿐, 판정은 실제 점검으로.** 신호가 뜨면 카테고리 루트/마운트 생존을 확인한다.

   | 점검 결과 | 카드 | 파괴적 조치 |
   |---|---|---|
   | 루트 접근 불가 | "원격 드라이브 연결 끊김" (하위 도서 숨김) | 전부 비활성 |
   | 루트 정상 | "대량 이동/삭제 의심" (폴더 이름 변경 등) | 확인 절차 후에만 |
   | 기준 미달 | 일반 "파일 없음" 카드 | 보통대로 |

   루트 접근 불가는 숫자와 무관하게 그 자체로 확정.
4. **여러 카테고리가 같은 시간대에 루트 접근 불가**(같은 rclone 리모트 공유 등)면 카테고리별 카드 대신
   시스템 카드 1장 "원격 드라이브 연결 끊김 (카테고리 N개)"로 올린다.
5. **구현 전 확인**: 스캐너에 이미 마운트 끊김 시 삭제 처리를 막는 방어가 있는지 확인하고, 있으면 그 판정을 재사용.

#### 고정값으로 시작, 나중에 사용자 지정 가능하게
사용자(개발자)는 설정보다 고정값을 선호하지만(원격 스캔 1스레드 고정 사례), 커뮤니티에서는 범위 지정
요청이 나올 가능성이 높다. 그래서 **지금은 고정값, 구조는 설정화 가능하게** 만든다.
- 기준값(20%, 20건)은 **한 곳의 이름 있는 상수**로 두고, 코드 곳곳에 숫자를 흩뿌리지 않는다.
- 값은 **조회 함수 하나**(예: `get_mass_missing_thresholds(db_type, library_id)`)를 통해서만 읽는다.
  지금은 상수를 반환하지만, 나중에 전역 설정(settings) → 카테고리별 덮어쓰기 순으로 확장할 자리를 남긴다.
  카테고리 인자는 지금부터 받아 둔다 (카테고리마다 성격이 달라 카테고리별 요청이 나올 가능성이 큼).
- 설정화할 때도 **루트 접근 불가 판정은 설정 대상이 아니다.** 안전장치라 끌 수 없게 한다.
- 설정 UI는 요청이 실제로 들어올 때 만든다.

### 결정: 플러그인 문제 카드 계약 (2026-09-29)
플러그인도 문제 카드를 "삽입"할 수 있도록 **새 선택 계약**을 만든다. 기존 캐시(`self.cache_get`)·
DB 게이트웨이(`self.get_db_gateway`)처럼 **베이스 클래스 헬퍼 메서드**로 제공한다.

```python
# 문제 발생 (같은 대상·코드로 다시 부르면 횟수만 증가)
self.report_problem(
    code="token_expired",               # 플러그인 안에서만 유일하면 됨
    severity="action_required",         # notice / action_required
    title="Spotify 토큰 만료",           # 문구는 플러그인이 직접 제공
    detail="설정에서 다시 로그인하세요.",
    db_type="general", target_type="book", target_id=123,   # 선택
    action_id="reauth",                 # 선택: 버튼 → 기존 액션 RPC
)

# 해결 (다음에 성공했을 때)
self.resolve_problem(code="token_expired", target_type="book", target_id=123)
```

1. **코어는 저장·표시만.** 플러그인 코드의 의미를 코어가 해석하지 않으므로 제목/설명은 플러그인이
   제공한다 (코어 = 게이트웨이 + 계약 원칙).
2. **충돌 방지 자동화.** 코어가 `source=plugin:<plugin id>`를 붙이고 코드를 `<plugin id>:<code>`로
   저장한다 (플러그인 id 네임스페이스 규칙과 같은 원리).
3. **조치 버튼은 기존 경로 재사용.** 새 API 없이 `/api/media/context-menu/book/plugins/action` +
   `action_id`로 연결한다.
4. **노출 범위 = 관리자만.** 특정 사용자에게 보내는 개인 알림 통로로 쓰이지 않게 한다.
5. **대량 발생 판정(20% AND 20건, 원인 접기)은 적용하지 않는다.** 그 규칙은 스캐너 `file_missing`에
   특화된 것이고, 코어가 플러그인 문제에 이런 제약을 걸면 플러그인이 할 수 있는 범위가 너무 좁아진다.
   플러그인 문제는 플러그인 id 단위 카드로만 묶는다 (`group_key = plugin:<id>|code`).
6. **최소한의 남용 방지.**
   - 플러그인별 열린 문제 수 상한(예: 1,000건), 넘으면 오래된 것부터 정리.
   - 카드에 플러그인 이름을 항상 표시해 출처를 알 수 있게 한다.
   - 플러그인 비활성화/삭제 시 해당 문제는 숨기고 정리한다.
7. **호환성.** 추가만 하는 선택 계약이라 기존 플러그인 동작은 바뀌지 않는다.
   - `docs/guide_plugins.md` 호환성 매트릭스에 새 버전 행 추가 + 영문판(`guide_plugins_en.md`) 동기화.
   - 플러그인은 `hasattr(self, 'report_problem')`으로 기능 감지 후 사용.
   - 문서화되지 않은 기능은 죽은 기능 — 샘플 플러그인 1개에 실제 사용 예를 넣는다.

## 4. 심각도
| 등급 | 예 | 표시 |
|---|---|---|
| 자동 복구됨 | 추가일 누락 보정 | 큐에 안 올림, 요약만 ("오늘 자동 복구 3건") |
| 참고 | 커버 추출 실패 몇 권 | 큐에 있으나 빨간 점 없음 |
| 조치 필요 | 마운트 끊김, 요약 테이블 멈춤 | 빨간 점 + 큐 최상단 |

## 5. 수명 관리
- **자동 해제**: 다음 스캔에서 대상이 성공하면 해당 행 해결 처리 → 묶음 개수 감소 → 0이면 카드 소멸.
- **알고 있음(음소거)**: 묶음 단위. 새 대상이 추가되면 다시 표시.
- **보관**: 해결된 행은 30일 후 정리.

## 6. 진단 버튼 (도서 상세)
도서 상세에 [진단]을 두고 체크리스트로 보여 준다. 실패 항목이 곧 원인, 그 아래 버튼이 해결책.

```
✓ DB 기록 정상
✗ 파일 존재 — <경로> 없음
✓ 원격 드라이브 연결
→ 파일이 이동된 것 같습니다. [재스캔] [휴지통으로 이동]
```

`services/library_diagnostics_service.py`(현재 MCP 전용 진단 쿼리)를 책 1권 단위로 재사용 가능.

## 7. 스캔 알림 → 종합 알림센터 개편
문제 카드만 따로 만들면 알림 창구가 또 하나 늘어난다. **현재 "스캔 활동" 팝오버 자체를
종합 알림센터로 개편하는 것까지 이 계획의 범위로 본다.**

### 현재 상태 (2026-09-29 기준)
상단 〰 아이콘 → `static/js/scan_activity_status.js`가 `/api/system/status`를 **2초마다 폴링**해
한 팝오버에 아래를 각자 다른 방식으로 섞어 그린다.

| 출처 | 내용 | 특징 |
|---|---|---|
| `raw_status.running` / `pending` | 실행 중 / 대기 중 스캔 | 메모리 큐 상태, 끝나면 사라짐 |
| `raw_status.recent_book_scans` | 최근 끝난 도서(선택) 스캔 | 도서 스캔만 남음, 카테고리 스캔 완료/실패 기록은 목록에 없음 |
| `tts_pregen` | 음성 미리 만들기 진행/완료/실패 | 완료·실패 시 토스트(`notifyPregenTransitions`)도 별도로 띄움 |
| `system_warnings` | 계속 실패 중인 작업 (관리자) | `SystemHealthService`, 빨간 점 |
| `tasks` (문자열) | DB 튜닝 등 기타 | 문자열 목록 fallback |

문제점:
- 항목마다 모양·수명·알림 방식(점/토스트/목록)이 제각각이다.
- **카테고리 스캔이 실패해도 끝나면 흔적이 없다** (큐 결과는 DB에 있지만 화면에 안 나옴).
- 이름이 "스캔 활동"이라 음성 생성·시스템 경고가 들어가기엔 맞지 않는다.
- 2초 폴링이 모든 로그인 사용자에게 돈다 (사용자 수가 늘면 비용).

### 목표 구조
알림센터 항목을 **세 종류**로 정리하고, 모두 같은 항목 스키마로 그린다.

| 종류 | 예 | 수명 |
|---|---|---|
| 진행 중 작업 | 스캔, 음성 생성, DB 튜닝 | 끝나면 "최근 완료"로 이동 |
| 최근 완료 기록 | 카테고리 스캔 완료(추가 N권), 음성 생성 완료, 실패 | 일정 기간/개수 후 정리, 읽음 처리 가능 |
| 문제 카드 | 1·3번의 묶음 카드 | 원인 해결 시 자동 소멸 |

공통 항목 스키마(초안): `kind`, `source`(scan/tts/system/plugin), `severity`, `title`, `detail`,
`target`, `actions[]`, `progress`, `created_at`, `updated_at`, `read`.

- 아이콘 표시 규칙 통일: 진행 중 = 주황 점(깜빡임), 조치 필요 = 빨간 점(고정), 그 외 = 없음.

### 결정: 탭 없이 한 목록, 종류별 색 구분 (2026-09-29)
진행 중 작업 / 완료 기록 / 문제 카드를 탭으로 나누지 않고 **한 목록**에 두되, 종류별로 색을 달리한다.

| 종류 | 색 | 예 |
|---|---|---|
| 에러 / 조치 필요 | 빨강 | 문제 카드, 시스템 경고, 스캔 실패 |
| 진행 중 | 주황 | 스캔 중, 음성 생성 중 |
| 신규 추가 | 파랑 | "스캔 완료 · 새 도서 3권", "음성 준비됨" |
| 완료 (변화 없음) | 초록 | 수동 스캔 "완료 · 변화 없음" |
| 취소 / 지난 항목 | 회색 | 취소된 작업 |

- **색만으로 구분하지 않는다**: 아이콘 + 짧은 라벨(에러/진행/신규/완료)을 함께 둔다 (색각 이상, 흑백 화면 대비).
- 목록 순서: 에러/조치 필요 → 진행 중 → 최근 완료(신규/완료/취소, 최신순).
- 색은 CSS 토큰으로 정의해 테마(라이트/다크, 테마 외부화 작업)와 맞춘다.
- **일관성 주의**: 현재 도서 카드의 최근 추가 배지는 새 작품 `NEW`가 빨강(`.book-card-recent-badge.is-new`)이다.
  알림센터에서 빨강 = 에러로 정하면 의미가 충돌하므로, 알림센터 구현 시 `NEW` 배지를 파랑 계열로
  맞출지 함께 결정한다.
- 토스트는 "보고 있는 동안 끝난 작업"에만 쓰는 현재 규칙을 공통 규칙으로 승격.
- 스캔 완료 기록에 **결과 요약**을 넣는다: "리디(GDS,소설) 스캔 완료 · 새 도서 3권 · 실패 1권".
  이 "새 도서 N권"은 카드의 NEW/+N권 배지(최근 추가 배지)와 자연스럽게 이어진다.
- 모바일: 현재 ☰/드로어 푸터 미러 점(`data-role="scan-activity-mirror"`) 구조를 그대로 재사용.

### 결정: 최근 완료 기록 (2026-09-29)
1. **저장 위치: 기존 `scan_history` 재사용, 결과 요약 컬럼(JSON) 하나만 추가.**
   - 예: `{"new_books": 3, "errors": 1, "report_file": "80_20260929....json"}`
   - 값 출처: `tools/scanner/engine.py`의 `detected_new_books`(현재 웹훅으로만 나감),
     `library_errors`(현재 `utils/report_helper.py` 리포트 JSON으로만 저장).
   - 알림센터는 `scan_history` + TTS 미리 만들기 작업 테이블을 어댑터로 읽어 공통 항목으로 변환.
   - 이유: 작업 단위 기록(종류/상태/오류/시각)은 이미 있고 빠진 건 결과 요약뿐이다.
     알림 전용 테이블을 따로 두면 같은 내용을 두 번 쓰게 된다.
   - 컬럼 추가는 `docs/change_db_guide.md` 절차(`_SCHEMA_SQL`)를 따른다.
2. **표시 대상: 변화가 있을 때만.**
   - 새 도서 / 에러 / 실패 / 취소가 있으면 표시.
   - "변화 없음"으로 끝난 자동 작업(lazy_scan, 예약 스캔)은 숨긴다. 이력 테이블에는 남는다.
   - 사용자가 직접 누른 스캔은 변화가 없어도 "완료 · 변화 없음"으로 표시한다
     (눌렀는데 아무 반응이 없으면 불안하므로).
   - 자동/수동 구분 방법(큐 kwargs에 트리거 출처가 있는지)은 구현 시 확인.
   - 이유: lazy_scan은 매시간 돌아 2개월에 약 100건이 쌓였다. 전부 보여 주면 목록이 의미를 잃는다.
3. **보관: 알림센터 7일(최대 50건) / `scan_history` 90일.**
   - `scan_history`는 현재 정리 로직이 전혀 없다(홈 서버 약 870행/2개월). 90일 지난 행 정리를 추가한다.
   - 정리 시점(서버 시작 마이그레이션 vs 스캔 완료 후)은 구현 시 결정.

### 결정: 알림 일괄 지우기 (2026-10-02) ✅ 완료 (2026-10-02, 테스트 서버 MariaDB 실측, 미커밋)
> 구현 메모: `notification_service.clear_notifications` / `undo_clear`, API `POST /api/notifications/clear`, `POST /api/notifications/clear/undo`
> (`{previous_cleared_ms, muted_group_keys}`; 카드 해제는 관리자 세션일 때만). 버튼 표시 판단은 `notification_render.clearableCount`(서버 규칙과 같음).
> 되돌리기 토스트를 위해 공용 `showToast(message, type, options)`에 선택 인자(`actionLabel`/`onAction`/`duration`)를 추가 — 기존 호출은 그대로.
> 참고 카드 음소거는 '그 시점 개수까지' 숨김이라, 이후 대상이 늘면 다시 보인다(기존 규칙). 실제 로그인 화면 확인은 아직(하네스/API만).
팝오버 머리말에 **[지우기] 버튼 하나**. 3단계 보완으로 보고 **5단계 착수 전에 먼저 구현**한다.

| 종류 | [지우기] 동작 |
|---|---|
| 진행 중 (스캔·음성 생성) | 건드리지 않음 (끝나면 알아서 최근 완료로 이동) |
| 최근 완료 (스캔 결과·음성 준비됨·실패·취소) | **목록에서 숨김** |
| 참고(notice) 문제 카드 (파일 없음·손상·표지 실패 등) | **일괄 "알고 있음"(음소거)** — 새 대상이 생기면 다시 보이는 기존 규칙 그대로 |
| 조치 필요(action_required) 카드 (연결 끊김·대량 사라짐·시스템 작업 실패) | **건드리지 않음** — 원인 해결 시 자동 소멸, 개별 "알고 있음"만 허용 ("빨간 점은 조치 필요에만" 원칙) |

구현 메모:
- 기록은 지우지 않는다. 사용자별 설정 `NOTIFICATIONS_CLEARED_MS`(읽음 처리 `NOTIFICATIONS_LAST_SEEN_MS`와 같은 방식, user_settings) 하나를
  저장하고, `build_notifications`에서 `updated_at <= cleared`인 **최근 완료** 항목만 뺀다.
  `scan_history`(관리자 이력, MCP `get_scan_history` 데이터)는 그대로 둔다. 관리자가 여럿이면 각자 따로 지워진다.
- 참고 카드 음소거는 카드 단위 공용 상태(`problem_groups`)라 **모든 관리자에게 적용**된다 — 버튼을 누른 관리자만의 숨김이 아님. (이 차이를 의식할 것)
- API: `POST /api/notifications/clear` (login_required; 참고 카드 음소거는 관리자일 때만 수행).
  응답에 직전 `cleared_ms`와 음소거한 group_key 목록을 돌려줘 토스트 [되돌리기]로 복원 (`cleared_ms` 되돌림 + 해당 카드 unmute).
- 버튼은 지울 것(최근 완료 또는 참고 카드)이 있을 때만 보인다. 일반 사용자는 본인 음성 완료 기록만 지워진다.
- 테스트: 어댑터 필터(시각 경계, 진행/조치 필요 유지), API(일반 사용자는 음소거 안 함), 되돌리기.

## 8. 구현 순서 (확정, 2026-09-29)
각 단계는 **따로 배포해도 동작하는 단위**로 나눴다. 앞 단계의 결과물 위에 다음 단계가 올라간다.
단계마다 끝나면 이 문서의 해당 항목에 `✅ 완료 (날짜)`를 붙인다.

### 0단계 — 선행 정리 (이 설계가 나온 세션의 미커밋 작업) ✅ 완료 (2026-09-29, 커밋 `4a91006`, 홈 서버 수동 배포)
- 커밋 대상: 최근 추가 배지(`SeriesService.annotate_recent_additions`, `static/js/ui.js`),
  요약 테이블 NULL 방어(`repositories/*/series_repository.py` `COALESCE(MAX(created_at), '')`),
  추가일 자동 보정(`_backfill_books_created_at`), `SystemHealthService` + 관리자 빨간 점, 이 문서.
- 같은 작업 트리에 TTS 등 다른 미커밋 작업이 섞여 있으니 **커밋 단위를 나눠서** 올린다.

### 1단계 — 데이터 기반 (화면 변화 없음) ✅ 완료 (2026-10-02, 테스트 서버 MariaDB 실측, 미커밋)
> 구현 메모: 시각 컬럼은 `*_ms`(epoch ms, `tts_pregen`과 같은 방식)로 저장하고 서비스에서 타임존 포함 ISO로 변환.
> 플러그인 계약(6단계)을 위해 `title`/`detail` 컬럼을 미리 둠. 행 `status`는 open/resolved만 — 음소거는 `problem_groups`.
> 시스템 경고는 `code='system_task_failed'`, `group_key='system_task_failed|general|-'` 카드 1장.
> 예전 `SYSTEM_HEALTH_*` settings 행은 서버 시작 마이그레이션(`_migrate_system_health_settings`)이 옮기고 지움.
> 해결 행 30일 정리는 서버 시작 시(`_purge_resolved_problems`). 테스트: `tests/test_problem_service.py`, `tests/test_system_health_service.py`.
1. `problem_occurrences` / `problem_groups` 테이블 생성 (3장 스키마 초안).
   - `docs/change_db_guide.md` 3번: `_SCHEMA_SQL`(SQLite) **와** `MARIADB_CENTRAL_SCHEMA`(MariaDB) 둘 다.
2. 리포지토리 `repositories/{sqlite,mariadb}/problem_repository.py`:
   UPSERT(재발 시 count/last_seen 증가), resolve, 카드 목록, 카드 안 시리즈별 집계(`series_key`),
   도서 목록 페이지네이션, 해결 행 30일 정리.
   - **삭제 연동 정리**: 카테고리 삭제 시 그 카테고리의 문제 기록/카드 상태 삭제, 도서 삭제(휴지통 비우기)
     시 해당 도서 행 해결 처리. 이게 없으면 지운 카테고리의 카드가 영원히 남는다.
3. 서비스 `services/problem_service.py`:
   - `report()` / `resolve()` / `track()` (예외 → report, 성공 → resolve)
   - 코드 카탈로그: 코드 → i18n 키, 기본 심각도, 조치 목록
   - `get_mass_missing_thresholds(db_type, library_id)` — 지금은 상수(20%, 20건) 반환
   - 시각은 타임존 포함 ISO 형식
4. `SystemHealthService` 흡수: `track()` 호출부(스캔 완료/휴지통/카테고리/마이그레이션 4곳)는 그대로,
   내부 저장만 `problem_service`(`target_type='system'`)로 교체. 기존 `SYSTEM_HEALTH_*` settings 행은 정리.
- **완료 기준**: 단위 테스트 통과, 테스트 서버에서 기존 빨간 점 경고가 새 저장소로 그대로 동작.

### 2단계 — 스캔 완료 기록 (7장 "결정: 최근 완료 기록") ✅ 완료 (2026-10-02, 테스트 서버 MariaDB 실측, 미커밋)
> 구현 메모: `scan_history.result_summary`(JSON). 카테고리 스캔 = `{"new_books", "errors", "report_file"}`
> (엔진 `_scan_library_internal(result_summary=)` → `scan_library` 반환 → `run_scan_job` 반환 → 워커),
> 선택 도서 스캔 = `{"books", "succeeded", "errors"}`(일부 실패 시 예외의 `.result_summary`로 전달).
> lazy_scan / cover_scan / gdrive_copy / 오디오북·영상 스캔은 요약 없음(NULL) — 필요해지면 같은 경로로 추가.
> 트리거는 kwargs `trigger_type`: `manual`(사용자), `cron`(예약 — 기존 값 유지, 계획의 'schedule' 대신),
> `lazy`(예약 lazy_scan), `webhook`(`/api/webhook/scan`, gd-poller 등). 없으면 = 예전 행 → 자동 취급 권장.
> 덤으로 `scan_library`가 엔진과 같은 오류 리포트를 한 번 더 저장하던 중복을 없앰(`_save_report_unless_saved`).
> 90일 정리 = 서버 시작 시 `_purge_old_scan_history`. 테스트: `tests/test_scan_result_summary.py`.
1. `scan_history`에 결과 요약 JSON 컬럼 추가 (`_SCHEMA_SQL`).
2. `tools/scanner/engine.py`의 `detected_new_books` 수 / `library_errors` 수 / 리포트 파일명을
   `services/scanner_queue.py` 작업 결과 기록(`update_task_result` → `record_scan_history`)까지 전달.
3. **수동/자동 구분 추가** — 현재 큐 작업에는 트리거 출처 정보가 없다(2026-09-29 확인,
   `ScannerQueue.enqueue`). 스캔을 등록하는 곳마다 `trigger='manual'|'schedule'|'lazy'|...`를 kwargs로 넘긴다.
4. `scan_history` 90일 정리 추가 (시점: 서버 시작 마이그레이션 쪽 권장 — 스캔 완료 경로를 무겁게 하지 않음).
- **완료 기준**: 카테고리 스캔 후 `scan_history`에 새 도서 수/에러 수가 남음.

### 3단계 — 알림센터 개편 (기존 출처만, 문제 카드 전) ✅ 완료 (2026-10-02, 하네스 화면 확인 + 테스트 서버 실데이터 어댑터 확인, 미커밋)
> 구현 메모: 서버 어댑터 `services/notification_service.py` (`build_notifications`), 렌더 순수 함수 `static/js/notification_render.js`
> (node 테스트 `tests/test_notification_render.mjs`), 폴링·DOM은 기존 `scan_activity_status.js`. 문구는 서버가 i18n 키+변수(`detail: [{key, vars}]`)로
> 내려주고 화면이 번역한다(스캐너 진행 단계/오류 원문은 `raw_detail`로 그대로). 시스템 경고는 작업별 한 줄(문제 카드 `system_task_failed`는 제외),
> 그 밖의 열린 문제 카드는 일반 카드 줄로 이미 표시된다(4단계에서 상세/조치 연결).
> 읽음 = 사용자별 `NOTIFICATIONS_LAST_SEEN_MS`(user_settings), 팝오버를 **닫을 때** `POST /api/notifications/seen`.
> 토스트 = 직전 폴링에서 진행 중이던 `track_key`가 최근 완료로 넘어온 항목만. 아이콘은 종(fa-bell)으로 교체.
> 덤: 머리말이 두 줄이라 목록 맨 아래가 잘리던 기존 문제를 flex 레이아웃으로 수정.
> 남은 것: 음성 미리 만들기 "최근 완료"는 아직 웹 프로세스 메모리(30분) 기준 - 7일 보관하려면 작업 테이블에서 읽도록 바꿔야 함.
1. 서버 어댑터: `/api/system/status`에 공통 스키마 `notifications[]` 추가
   (진행 중 스캔, 최근 완료 기록, TTS 미리 만들기, 시스템 경고). **audience로 걸러서** 내려준다.
   전환 기간에는 기존 필드(`raw_status`, `tts_pregen`, `system_warnings`)도 유지.
2. `static/js/scan_activity_status.js` 팝오버를 공통 렌더러 하나로 교체:
   한 목록, 종류별 색 + 아이콘 + 라벨, 순서(에러 → 진행 → 최근 완료), 이름 "알림"(i18n ko/en),
   일반 사용자는 항목 없으면 아이콘 흐리게, 모바일 미러 점 유지.
3. 읽음 처리: 사용자별 "마지막으로 확인한 시각" 하나로 시작 (`SettingsService.set_user_value`) —
   항목별 읽음 테이블은 필요해질 때.
4. 도서 카드 `NEW` 배지 색을 파랑 계열로 조정 (빨강 = 에러와 충돌 방지).
- **완료 기준**: 지금 팝오버에 나오던 내용이 전부 새 목록에 나오고, 카테고리 스캔 결과가 "최근 완료"로 보임.

### 4단계 — 스캐너 문제 기록 + 문제 카드 ✅ 완료 (2026-10-02, 테스트 서버 MariaDB 실측: NAS 마운트 내림/복구 + 임시 카테고리 대량 사라짐, 미커밋)
> 구현 메모:
> - **기존 방어 확인 결과**: ① 스캔 시작 시 루트 접근 실패 → 스캔 실패(카드 없음) ② 폴더 순회 오류 → 삭제 동기화 생략
>   ③ 파일 0개 → 삭제 중단(단 early return이라 scanner_progress가 남음). 부분 마운트 장애(일부 폴더만 빈 목록)는 못 막았다.
> - 판정 위치: 엔진 삭제 동기화 **직전** `services/scan_problem_service.gate_deletions` → (진행/'root'/'mass').
>   'root'면 삭제 동기화 자체를 건너뛰고(복구/7일 비우기 포함), 'mass'면 새로 사라진 도서의 휴지통 이동만 보류.
>   이미 휴지통에 있는 도서는 판정·기록에서 뺀다(스캐너의 '사라진 도서' 목록엔 휴지통 도서도 들어 있음 - 실측에서 발견).
> - 코드: `file_missing`(이미 휴지통, 참고), `mass_missing`(보류, 조치 필요, [확인 후 휴지통으로]), `remote_unavailable`(카테고리 행),
>   `file_corrupt`(BadZipFile/Offset*), `cover_missing`(NoCover), `unknown`(그 밖). 4단계 계획의 file_missing=조치 필요 → 실제론 스캐너가
>   이미 휴지통으로 옮기므로 '참고'로 정함.
> - 문제 기록 쓰기는 스캔 트랜잭션 커밋 **후**(`engine._record_scan_problems`) - SQLite general은 도서와 같은 파일이라 잠금 충돌 방지.
> - 해제: `reconcile` (파일 다시 보임 / 도서 행 없어짐 / 다시 처리됐는데 오류 없음 / 루트 정상).
> - 여러 카테고리 동시 연결 끊김 → 알림 어댑터에서 한 줄로 접음. 원인 카드가 열린 카테고리의 '스캔 실패' 줄은 숨김.
> - API(관리자): `GET /api/problems/card`, `GET /api/problems/card/items`, `POST /api/problems/card/mute`, `POST /api/problems/card/confirm-trash`.
>   재스캔은 기존 `/scan`, `/scan-path`(동기), `/books/scan-batch` 재사용. UI = `static/js/notification_cards.js`.
> - MCP: `list_problems`, `get_problem_card` (읽기 전용). `propose_rescan`(Tier B)은 아직.
> - **발견, 손대지 않음**: 전체 스캔마다 휴지통 도서의 `deleted_at`이 다시 현재 시각으로 바뀌어(`handle_deleted_books`), 자주 스캔하는
>   카테고리는 '7일 뒤 자동 비우기'가 사실상 일어나지 않는다. 고치면 쌓인 휴지통이 한꺼번에 영구 삭제되므로 사용자 결정 필요.
- **범위: 일반/성인 도서 스캐너 먼저.** 오디오북/영상 스캐너는 구조가 달라 이 단계에서 제외하고,
  도서 쪽이 안정된 뒤 같은 코드 체계로 확장한다 (`db_type` 컬럼은 처음부터 있으므로 스키마 변경 불필요).
1. **먼저 확인**: 스캐너가 마운트 끊김 시 도서 삭제 처리를 이미 막는지. 있으면 그 판정을 재사용.
2. 발생 지점에 코드 부여: `file_missing`, `file_corrupt`, `remote_unavailable` (+ `series_key` 저장).
   다음 스캔에서 성공한 대상은 자동 해결.
3. 스캔 종료 시 대량 발생 판정 (3장 "결정: 대량 발생 기준") + 루트/마운트 점검 +
   여러 카테고리 동시 발생 시 시스템 카드 1장.
4. 알림센터에 문제 카드 연결: 카드 → 시리즈 줄 → 도서 목록(페이지네이션), 단계별 조치 버튼
   (모두 재스캔 / 시리즈 재스캔(기존 `scan_routes.py` 재사용) / 재스캔), 알고 있음(음소거),
   루트 접근 불가 시 파괴적 조치 비활성.
- **완료 기준**: 테스트 서버에서 rclone 마운트를 내렸을 때 카드 1장("원격 드라이브 연결 끊김")만 뜨고
  어떤 도서도 삭제/휴지통 처리되지 않음. 마운트 복구 후 다음 스캔에서 카드 자동 소멸.

- **기존 스캔 에러 리포트와의 관계**: `utils/report_helper.py`의 JSON 리포트(설정 > 리포트 탭)는
  이 단계에서는 **그대로 유지**한다 (문제 기록과 병행). 문제 카드가 안정되면 리포트 탭을
  문제 기록 조회 화면으로 바꾸고 JSON 리포트를 걷어낼지 그때 결정한다.

### 5단계 — 진단 버튼 + "관리자에게 알리기" ✅ 완료 (2026-10-02, 테스트 서버 MariaDB + 로그인 화면 실측, 미커밋)
> 구현 메모:
> - 진단: `services/book_diagnosis_service.diagnose_book` (일반/성인 도서). 점검 db → library → remote(`scan_problem_service.check_roots`, 스캐너와 같은 판정)
>   → file → format(zip 계열 중앙 디렉터리 / PDF 머리말만). 파일 시스템 점검은 15초 시간 제한(멈춘 rclone이 웹 스레드를 붙잡지 않게),
>   시간 초과는 '끊김'이 아니라 '느림' 결론. 실측: GDrive 도서 첫 진단 약 8초, 로컬 0.7초. `library_diagnostics_service`는 서재 단위 쿼리라 재사용 안 함.
>   조치는 재스캔만(파일 없음 → 폴더 재스캔 = 스캐너가 정상 경로로 휴지통 처리, 손상 → 그 권 재스캔). 수동 휴지통 이동 API는 만들지 않음.
>   API `GET /api/problems/diagnose`(관리자), MCP `diagnose_book`. 화면: 도서 메뉴 [진단](관리자, 낱권), 문제 카드 도서 줄 [진단], `static/js/book_diagnosis.js` + `diagnosis_render.js`.
> - 관리자에게 알리기: 잠정안대로 `code='user_report'`, `source='viewer'`, 참고 등급, `group_key=user_report|db|library`. 받는 쪽 `services/user_problem_report_service.py`
>   (카테고리 권한 확인, 사용자당 1시간 30건). `POST /api/problems/user-report`(login_required). 뷰어 쪽은 `view_manager.showViewerError` 한 곳에서
>   `static/js/viewer/report_problem.js`가 버튼을 붙인다(관리자에겐 [진단]). 스캐너가 판단할 근거가 없어 자동 해제 없음 → 카드 [해결됨]
>   (`POST /api/problems/card/resolve`, `ADMIN_RESOLVABLE_CODES`에 든 코드만). 테스트: `tests/test_book_diagnosis.py`.
1. 도서 상세 [진단]: DB 기록 / 파일 존재 / 원격 연결 체크리스트 + 결과별 조치 버튼
   (`services/library_diagnostics_service.py` 재사용).
2. 뷰어 등에서 일반 사용자에게 에러가 났을 때 그 자리에 한 줄 + [관리자에게 알리기].
   - 받는 쪽(잠정안): `problem_occurrences`에 `source='viewer'`, `code='user_report'`, `severity='notice'`로
     기록 → 관리자 알림센터의 일반 문제 카드로 표시. 같은 도서 재신고는 횟수만 증가.
- **완료 기준**: 일반 계정에서 없는 파일을 열면 알림 버튼이 보이고, 관리자 알림센터에 카드가 생김.

### 6단계 — 플러그인 계약 (3장 "결정: 플러그인 문제 카드 계약") ✅ 완료 (2026-10-02, 미커밋)
> 구현 메모:
> - 베이스 클래스 `plugins/metadata/base.py`에 `report_problem()`/`resolve_problem()` (추가만, 기존 플러그인 무영향) → `services/plugin_problem_service.py`.
>   코드 `<plugin id>:<code>`(영문/숫자/_ . - 64자), 출처 `plugin:<id>`, 카드 키 `plugin:<id>|<code>|-`(라우트의 `|` 2개 검증과 맞춤 - 계획의 'plugin:<id>|code'에 꼬리 `-`).
>   심각도는 notice/action_required만. 대상 기본 `system`(target_id `-`), `book`이면 코어가 시리즈/카테고리/경로를 채움.
> - 문구: 행의 `title`/`detail` 컬럼 + `context`(플러그인 id/이름/action_id/action_label). `list_cards`가 플러그인 카드에 `plugin` 정보를 붙이고(최근 행 1개 조회),
>   알림 항목 제목은 항상 `<플러그인 이름> · <제목>`. 조치는 카드 줄·도서 줄의 버튼 → 기존 액션 RPC, `context.source='problem_card'`, `open_url`이면 새 탭.
> - 남용 방지: 열린 문제 1,000건 상한(`PLUGIN_OPEN_LIMIT`, 넘으면 마지막 발생이 오래된 것부터 해결), 끄면 `on_plugin_disabled`(PluginService.toggle),
>   부팅 시 `cleanup_inactive_plugins`(start_all_plugin_background_services). 리포지토리에 출처 단위 쿼리 4개 추가(source 인덱스는 없음 - 플러그인 보고는 드물어 생략).
> - [해결됨]은 플러그인 카드에 없음(플러그인이 resolve, 관리자는 [알고 있음]). 대량 판정 미적용.
> - 샘플: `spotify_mood` 1.1.0 - 사용자 토큰 갱신 거절 시 `token_expired`(조치 필요, [다시 연결]=spotify_oauth_start), 갱신 성공·재연결·연결 해제 시 해결.
> - 문서: guide_plugins(ko/en) 매트릭스 1.1.2 행 + "관리자 알림 문제 카드" 절, plugin_checklist(ko/en), api_endpoints 10.5절, spec_db_schema·spec_scanner_logic·spec_feature_overview·guide_admin(ko/en), MCP 가이드, README.
>   테스트: `tests/test_plugin_problem_service.py`.
1. 베이스 클래스에 `report_problem()` / `resolve_problem()` 추가 (내부는 `problem_service`).
2. 코드 네임스페이스 자동 부여, 플러그인별 열린 문제 1,000건 상한, 비활성/삭제 시 정리.
3. 문서: `docs/guide_plugins.md` + `guide_plugins_en.md` (호환성 매트릭스 새 행), 샘플 플러그인 1개에 사용 예.
- 추가만 하는 계약이지만 **플러그인 계약 변경이므로 머지 전 사용자 확인** (코어 변경 거버넌스 규칙).
- **완료 기준**: 샘플 플러그인이 문제를 올리고 해결하는 흐름이 테스트 서버에서 동작.

### 7단계 — 필요해질 때만
- 폴링 부담 완화 (간격 조정, 변경 없을 때 가벼운 응답). SSE 등 푸시는 규모가 커질 때 재검토.
- 대량 발생 기준 설정화 (커뮤니티 요청이 오면: 전역 설정 → 카테고리별 덮어쓰기).
- (MCP 문제 기록 조회 도구는 아래 "MCP 병행 트랙"으로 이동)

### MCP 병행 트랙 (2026-09-29 추가)
커뮤니티에서 MCP 기능 평가가 매우 좋고, **대부분의 사용자가 도서 관리를 MCP로 하고 있다.**
따라서 알림센터/문제 카드 기능은 웹 화면과 **MCP 도구를 함께** 제공한다.

- **원칙: 기능 하나에 창구 둘.** 진단·문제 목록·스캔 결과 등은 서비스 계층에 한 번만 만들고, 웹 화면과
  MCP 도구가 같은 서비스를 부른다 (기존 `services/library_diagnostics_service.py` → `tools/mcp_server.py` 패턴).
  MCP 도구는 얇은 포장만 한다.
- **쓰기는 Tier B(제안 → 관리자 승인 대기열)로만.** AI가 재스캔/삭제를 직접 실행하지 않는다
  (기존 `propose_bulk_*` 도구와 `mcp_pending_changes` 승인 탭 재사용).
- `tools/mcp_server.py`의 stdout 보호 래퍼(`_quiet()`)를 새 도구에도 그대로 쓴다 (없으면 MCP 프로토콜이 깨짐).
- 로컬(SSH stdio) MCP 기준. 원격(Desktop) 접속 계획(`docs/plan_mcp_remote_desktop_access.md`)은 보류 중이라 범위 밖.

| 도구 | 시점 | 용도 |
|---|---|---|
| `check_library_health` | **단계와 무관, 1단계 전/사이에 먼저 가능** | 서재 건강 점검 한 번에 (아래) |
| `get_scan_history` | 2단계 뒤 | 최근 스캔 결과: 새 도서 수, 에러 수, 실패 |
| `list_problems` / `get_problem_card` | 4단계 뒤 | 열린 문제 카드, 카드 안 시리즈별 내역 |
| `diagnose_book` | 5단계와 동시 | 도서 상세 [진단]과 같은 체크리스트 |
| `propose_rescan` | 4단계 뒤 | 도서/시리즈/카테고리 재스캔 제안 (Tier B 승인) |

**`check_library_health` 점검 항목** — 2026-09-29 장애(요약 테이블 12일 정지)를 찾을 때 SSH 쿼리 스크립트를
5번 돌려야 했던 것을 한 번에:
1. 시리즈 요약 테이블 신선도: `series_summary_state.refreshed_at` vs 카테고리별 마지막 스캔 시각
   (예: "요약 테이블이 9/16 이후 갱신 안 됨").
2. 카테고리별 도서 수 vs 요약 테이블 행 수 대조 (예: 카테고리 80 "도서 3,409권 / 요약 0행").
3. 값이 비정상인 행 수: `created_at` NULL 등 (자동 보정 대상이 남아 있는지).
4. 현재 열린 경고 (`SystemHealthService`, 1단계 이후엔 `problem_service`의 system 항목).
- 구현 위치: `services/library_diagnostics_service.py` 확장 + `tools/mcp_server.py` 도구 1개.
- 같은 서비스를 나중에 관리자 화면(시스템 상태)에서도 부를 수 있다.

### 단계 공통 규칙
- 검증 경로: 로컬 테스트 → 테스트 서버(192.168.0.21, MariaDB, `test_deploy.py`) → 홈 서버(`deploy.py`).
  운영 DB 직접 쓰기는 권한 정책상 막혀 있으니 필요하면 사용자에게 명령을 넘긴다.
- 스키마 변경은 항상 `docs/change_db_guide.md`를 먼저 읽는다.
- 새 백그라운드 작업은 `track()`으로 감싼다 (조용한 실패 방지).
- 사용자 문구는 i18n(ko/en) 키로.
- **단계마다 테스트를 함께 추가**한다 (SQLite 기반 단위 테스트 + 테스트 서버 MariaDB 실측).
- 문제 조회/조치 API(재스캔, 음소거, 문제 목록 등)는 **전부 관리자 전용**(`@admin_required`).
  예외는 음성 미리 만들기처럼 audience가 본인인 항목 조회, 그리고 5단계 "관리자에게 알리기" 신고 API뿐.

## 미정 사항 (차근차근 결정)
- ~~발생 기록 저장소~~ → **결정됨 (2026-09-29): 신규 테이블. 3장 "결정: 발생 기록은 신규 테이블" 참고.**
- ~~묶음 키~~ → **결정됨 (2026-09-29): 카드 = 문제 종류 x 카테고리, 카드 안은 시리즈별로 접어 올림, series_key 저장. 3장 "결정: 묶는 기준" 참고.**
- ~~"짧은 시간 대량 발생"의 기준치~~ → **결정됨 (2026-09-29): 카테고리 스캔 1회 기준, 20% AND 20건, 고정값으로 시작(설정화 가능한 구조). 3장 "결정: 대량 발생 기준" 참고.**
- ~~일반 사용자의 "재스캔 요청" 처리 방식~~ → **결정됨 (2026-09-29): 만들지 않음, "관리자에게 알리기"만. 2장 참고.**
- ~~플러그인이 자기 문제 카드를 올릴 수 있게 할지~~ → **결정됨 (2026-09-29): `report_problem`/`resolve_problem` 선택 계약, 관리자 전용, 대량 발생 판정 미적용. 3장 참고.**
- ~~스캔 진행 상황과 문제 카드를 같은 목록에 둘지, 탭으로 나눌지~~ → **결정됨 (2026-09-29): 한 목록 + 종류별 색. 7장 참고.**
- ~~"최근 완료 기록"의 저장 위치와 보관 기간~~ → **결정됨 (2026-09-29), 7장 "결정: 최근 완료 기록" 참고.**
- ~~읽음 처리를 사용자별로 할지~~ → **결정됨 (2026-09-29): audience별. 2장 참고.**
- ~~일반 사용자에게 알림센터를 보여 줄지~~ → **결정됨 (2026-09-29): 하나의 센터 + audience 필터, 항목 없으면 아이콘 흐리게. 2장 참고.**
- ~~"관리자에게 알리기"를 받는 쪽~~ → **결정됨 (2026-10-02): 잠정안 그대로 (`source=viewer`, `code=user_report`), 관리자 [해결됨]으로 닫음. 8장 5단계 참고.**
- 폴링 유지 vs SSE 등 푸시 방식 → 잠정: 폴링 유지 (8장 7단계, 필요해질 때 재검토).

## 관련
- `services/system_health_service.py` — 현재 최소 구현 (`track`, 관리자 빨간 점)
- `services/db_migration_service.py` `_backfill_books_created_at` — 자동 복구 예시
- `static/js/scan_activity_status.js` — 현재 팝오버
- `services/library_diagnostics_service.py` — 진단 쿼리 재사용 후보
