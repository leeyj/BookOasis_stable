---
title: "MCP 서버 가이드"
project: "BookOasis"
category: "guide"
date: 2026-09-15
tags: [mcp, ai, claude, guide]
---

# 🤖 BookOasis MCP 서버 가이드

서재 규모가 커질수록(수만~수십만 권) 데이터 품질(빠진 표지·장르·태그, 흩어진 중복 시리즈 등)을 손으로 훑어보기가 사실상 불가능해집니다. BookOasis는 이를 위해 **읽기 전용 MCP(Model Context Protocol) 서버**를 내장하고 있어, MCP를 지원하는 AI 코딩 도구(Claude Code, Claude Desktop, Gemini CLI, OpenAI Codex CLI, Cursor 등 — MCP는 특정 회사 전용이 아닌 공개 표준입니다)라면 어떤 걸 쓰든 서재 데이터를 직접 조회하고 문제를 찾아 관리자에게 알려주게 할 수 있습니다.

- 전송 방식은 **로컬 stdio 전용**입니다 — 네트워크로 노출되지 않으며, BookOasis가 설치된 바로 그 서버에서 AI 도구가 `tools/mcp_server.py` 프로세스를 직접 실행해서 붙습니다. 별도 인증 설정이 필요 없습니다.
- v1은 읽기 전용 진단 툴만 제공했습니다. v1.1부터 **저위험(Tier A) 쓰기 툴**이, 바로 이어서 **대량 작업용 Tier B 제안→승인 큐**가 추가되었으며, 둘 다 기본적으로 꺼져 있고(§쓰기 툴 참고) 관리자가 명시적으로 켜야 동작합니다.
- 먼저 `pip install -r requirements.txt`로 `mcp` 패키지를 설치해야 합니다. 아래는 각 클라이언트별 등록 방법입니다 — 안 쓰는 도구는 건너뛰세요.

## 등록 방법

### 공통 — MCP 서버 정의 (JSON)

거의 모든 MCP 클라이언트는 결국 아래와 같은 형태의 JSON 블록으로 "이 명령을 실행하면 붙일 수 있는 stdio MCP 서버가 있다"를 등록합니다. 클라이언트마다 이 블록을 넣는 설정 파일 위치/이름만 다릅니다.

```json
{
  "mcpServers": {
    "bookoasis": {
      "command": "python3",
      "args": ["/path/to/media_server/tools/mcp_server.py"]
    }
  }
}
```

`/path/to/media_server`는 실제 BookOasis 설치 경로(절대경로)로 바꾸세요.

### Claude Code

```bash
claude mcp add bookoasis -- python3 /path/to/media_server/tools/mcp_server.py
```

등록 후 `claude mcp list`로 `✔ Connected`가 뜨는지 확인하세요.

### Claude Desktop

`claude_desktop_config.json`(macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`)을 열어 위 "공통 JSON" 블록을 `mcpServers` 항목에 추가하고 앱을 재시작하세요.

### Docker로 설치한 경우

Docker 배포는 `python3`가 컨테이너 안에만 있고 호스트에는 없는 경우가 많아서, `claude mcp add`를 호스트에서 그대로 쓰면 실패합니다. 대신 `docker exec`로 컨테이너 안의 `mcp_server.py`를 직접 실행하도록 등록하세요 — 이미지 자체는 손댈 필요 없습니다(`requirements.txt`에 `mcp` 패키지가 포함돼 있어 빌드 시 자동 설치됩니다).

```bash
claude mcp add bookoasis -- docker exec -i bookoasis python3 tools/mcp_server.py
```

- `bookoasis`는 기본 `docker-compose.yml`의 컨테이너 이름입니다. 이름을 바꿨거나 여러 개 띄워둔 경우(`bookoasis_test` 등) `docker ps`로 실제 컨테이너 이름을 확인해 바꿔주세요.
- **`-i`는 필수입니다** (표준입력을 열어둬야 MCP 클라이언트가 JSON-RPC 메시지를 컨테이너 안으로 전달할 수 있습니다). **`-t`는 절대 넣지 마세요** — TTY를 붙이면 터미널 제어 문자가 섞여 들어가 stdio 프로토콜이 깨집니다.
- 컨테이너가 꺼져 있으면 당연히 연결도 실패합니다 — 평소 BookOasis 웹 UI가 떠 있는 상태와 동일하게 컨테이너가 실행 중이어야 합니다.
- 공통 JSON 블록으로 쓰려면(Claude Desktop 등):
  ```json
  {
    "mcpServers": {
      "bookoasis": {
        "command": "docker",
        "args": ["exec", "-i", "bookoasis", "python3", "tools/mcp_server.py"]
      }
    }
  }
  ```

### 버전 확인과 업데이트 — MCP는 업데이트를 "안내"만 합니다

`get_version`으로 실행 중인 버전을 확인하고, `call_api`로 `/api/media/about`을 호출하면 GitHub 최신 버전과 비교한 업데이트 가능 여부를 볼 수 있습니다. **MCP 서버는 BookOasis 자신을 업데이트하거나 덮어쓰지 않습니다** — 이는 "코어/플러그인 소스 파일은 건드리지 않고 DB만 쓴다"는 설계 원칙 때문이며, Docker 컨테이너 안에서 실행되는 MCP가 자기 이미지를 교체할 수도 없습니다. 업데이트는 항상 호스트에서 직접 실행하세요. (AI에게 "업데이트가 있는지 확인하고 방법을 알려줘"라고 요청하면 안내까지만 해줍니다.)

- **Docker (GHCR 이미지):** `docker compose -f <사용 중인 compose 파일> pull` 후 `up -d` — 자세한 명령은 [설치 가이드](guide_installation.md)를 참고하세요.
- **Docker (직접 빌드):** `docker compose -f docker-compose.build.yml -f docker-compose.override.yml up -d --build`
- **네이티브 설치:** 소스를 갱신한 뒤 서비스를 재시작하세요.

### Gemini CLI / OpenAI Codex CLI / Cursor 등 기타 MCP 클라이언트

이들도 대부분 위와 동일한 `mcpServers` JSON 형태를 쓰지만, 설정 파일 이름·위치와 CLI 등록 명령(있다면)은 도구마다 다르고 계속 바뀔 수 있습니다. 각 도구의 최신 공식 문서에서 "MCP server 등록"을 찾아 위 공통 JSON 블록을 그대로 붙여넣으면 됩니다 — `command`/`args`만 맞으면 어떤 클라이언트든 동일하게 동작합니다.

개발 중 클라이언트 없이 툴 목록/스키마만 빠르게 확인하려면(공식 `mcp` 패키지 제공 인스펙터):

```bash
mcp dev tools/mcp_server.py
```

## 제공 툴

### 읽기 전용

| 툴 | 설명 |
| :--- | :--- |
| `search_books` | 제목/시리즈명으로 시리즈 검색 (장르/태그 필터, `sort`: asc/desc/date_desc/date_asc 지원; video 제외) |
| `get_random_book` | 서재에서 시리즈 1개를 서버에서 무작위로 선택 (video 제외) |
| `get_library_stats` | 전체 및 카테고리별 시리즈 수·도서 권수 통계 |
| `find_missing_cover` | 표지 이미지가 없는 도서 목록 |
| `find_missing_genre_and_tags` | 장르·태그가 모두 비어있는 도서 목록 |
| `find_missing_offsets` | 페이지 오프셋 캐시가 없어 재스캔이 필요한 zip/cbz 도서 목록 (rclone/GDrive 등 원격 마운트 파일은 자동 제외) |
| `find_duplicate_series` | 동일한 시리즈명이 서로 다른 카테고리 2곳 이상에 흩어진 케이스 |
| `list_problems` | 알림센터의 열린 문제 카드 목록 (파일 없음·대량 사라짐 보류·원격 드라이브 끊김·파일 손상·백그라운드 작업 실패·사용자 신고·플러그인 문제 등, 플러그인 카드는 `plugin`에 이름/제목/설명) |
| `get_problem_card` | 문제 카드 하나의 시리즈별 내역, `series_key`를 주면 그 시리즈의 도서 목록 |
| `diagnose_book` | 도서 1권 진단: DB 기록 / 원격 연결 / 파일 존재 / 파일 형식 체크리스트와 원인·권장 조치 (읽기 전용) |
| `get_version` | 실행 중인 BookOasis 버전(VERSION 파일 기준) 조회 |
| `run_readonly_query` | 서재 DB에 읽기 전용(SELECT/WITH/EXPLAIN/PRAGMA/SHOW/DESCRIBE) SQL을 직접 실행 |
| `read_logs` | `logs/` 폴더의 서버 로그를 끝에서부터 최근 N줄 조회 (검색어 필터 지원) |
| `call_api` | 기존 GET REST API(`docs/api_endpoints.md`)를 그대로 호출 |

### 쓰기 (Tier A — 저위험, 기본 비활성화)

| 툴 | 설명 |
| :--- | :--- |
| `update_book_metadata` | 시리즈의 장르/태그/작가/출판사/요약/링크 등을 부분 수정 (전달하지 않은 필드는 유지). `<`/`>` 문자와 `http(s)://`가 아닌 링크는 거부됩니다(§입력 검증 참고) |
| `bulk_set_favorite` | 도서 id 목록에 대한 즐겨찾기 일괄 등록/해제 (1회 최대 500건) |

### 쓰기 (Tier B — 대량 작업, 즉시 실행하지 않고 제안만 생성)

| 툴 | 설명 |
| :--- | :--- |
| `propose_bulk_book_metadata_update` | 여러 시리즈의 메타데이터 일괄 수정을 "제안"만 함(즉시 반영 안 됨) |
| `propose_bulk_set_favorite` | 500건 초과 즐겨찾기 일괄 등록/해제를 "제안"만 함(즉시 반영 안 됨) |

`find_duplicate_series`는 정확히 같은 시리즈명만 잡습니다. 오타나 표기가 다른 유사 시리즈명까지 찾으려면 `search_books`로 Claude가 직접 탐색·판단하게 하는 편이 낫습니다 — 이런 퍼지 매칭 판단이야말로 MCP로 AI에게 맡기는 이유입니다.

### `run_readonly_query` — 스키마를 모르면 먼저 물어보세요

미리 만들어진 진단 툴로 커버되지 않는 새 조건은 이 툴로 즉석에서 조회하면 됩니다. 테이블 구조가 궁금하면 먼저 `PRAGMA table_info(books)` 같은 스키마 조회부터 해보세요. 안전장치는 2단계입니다:

1. **앱 레벨**: SQL이 `SELECT`/`WITH`/`EXPLAIN`/`PRAGMA`로 시작하지 않거나, 세미콜론으로 여러 구문이 붙어있거나, `INSERT`/`UPDATE`/`DELETE`/`DROP` 등 쓰기 키워드가 포함되면 즉시 거부됩니다.
2. **DB 레벨(진짜 안전판)**: sqlite 모드는 매번 별도의 OS 레벨 읽기전용 커넥션(`file:...?mode=ro`)을 열어 실행합니다 — 1번 검증이 뚫려도 파일에 물리적으로 쓸 수 없습니다. MariaDB 모드는 읽기전용 계정이 따로 없어서, 커넥션을 빌린 동안만 `SET SESSION TRANSACTION READ ONLY`를 걸어 서버가 쓰기를 거부하게 만들고 끝나면 원복합니다(MariaDB 쪽이 sqlite보다 방어가 한 단계 약합니다 — 읽기전용 계정을 별도로 만들 계획은 없습니다, 어차피 신뢰된 운영자 1인 전용 로컬 stdio 서버라서요).

### `call_api` — 진단 전용 툴로 안 되는 건 기존 API를 그대로 쓰세요

`docs/api_endpoints.md`에 정리된 기존 GET 엔드포인트를 그대로 호출합니다. 예:
```
call_api(path="/api/media/list", query_params={"type": "general", "library_id": "all", "limit": 5})
```
- **GET만 가능합니다** — SQL 툴의 SELECT-only 검증처럼 앱이 따로 걸러내는 게 아니라, 이 툴 자체가 GET 요청을 보내는 코드만 갖고 있어서 애초에 다른 HTTP 메서드를 부를 방법이 없습니다.
- 내부적으로 별도의 경량 Flask 앱을 만들어 관리자 계정으로 세션을 주입해서 호출합니다(실제 서버 프로세스와 무관한 in-process 호출 — 이미 떠 있는 웹 프로세스와 충돌하지 않습니다). 그래서 성인 서재/`admin_only` 플러그인 데이터도 제약 없이 조회됩니다.
- `/api/`로 시작하지 않는 경로(`/login` 등)는 거부됩니다.

## 쓰기 툴 — 설계 원칙 (Tier A / Tier B)

읽기 전용 진단 툴이 호평을 받으면서, 다음 단계로 "찾은 문제를 AI가 바로 고치게 할 수 없나"라는
요청이 나왔습니다. 다만 AI 에이전트가 서재 데이터를 잘못 고치거나, 나아가 **코어 코드나 다른
플러그인**을 건드릴 수 있다는 우려가 있어 아래 원칙으로 범위를 좁혔습니다.

1. **코어/플러그인 소스 파일은 절대 건드리지 않습니다.** 쓰기 툴은 파일시스템에 전혀 쓰지 않고,
   오직 서재 DB만 — 그것도 이미 검증되어 기존 REST API가 쓰는 것과 동일한 서비스/리포지토리
   메서드를 통해서만 — 변경합니다. 스키마/DDL 변경은 여기서 다루지 않으며 앞으로도 다루지
   않습니다(`services/db_migration_service.py`가 유일한 진입점이라는 기존 원칙 유지).
2. **범용 쓰기 SQL 툴은 만들지 않습니다.** `run_readonly_query`와 대칭되는 "아무 SQL이나 실행"
   툴은 코어를 지키는 핵심 안전장치이므로 의도적으로 제공하지 않습니다. 대신 목적이 분명한
   좁은 툴(`update_book_metadata`, `bulk_set_favorite`)만 하나씩 추가합니다.
3. **위험도 2단계 분리.**
   - **Tier A (저위험, 즉시 실행)**: `update_book_metadata`/`bulk_set_favorite`처럼 이미
     존재하는 파라미터화된 서비스 메서드를 그대로 호출하는 수준. 대량이 아니라 개별/소규모
     (최대 500건) 수정만 다룹니다.
   - **Tier B (대량 작업, 제안→승인 큐)**: `propose_bulk_book_metadata_update`/
     `propose_bulk_set_favorite`는 MCP가 직접 DB를 바꾸지 않고 `mcp_pending_changes`
     테이블에 변경 전/후 값 미리보기만 만들어 대기시킵니다. 관리자가 설정 > **MCP 승인
     대기** 탭에서 내용을 검토한 뒤 승인 버튼을 눌러야만 실제로 반영되고, 거부하면 DB에는
     아무 것도 쓰이지 않습니다. 재스캔 트리거/삭제성 작업은 이번 범위에 포함하지 않았습니다
     — 필요해지면 같은 큐에 tool_name만 추가하면 되는 구조입니다. 이 화면이 쓰는 관리자
     API(`GET/POST /api/admin/mcp-pending-changes...`)는 `docs/api_endpoints.md` §9.5에
     정리되어 있습니다.
4. **관리자 킬스위치.** 설정 > 일반 설정의 "MCP 쓰기 도구 허용"(`MCP_WRITE_ENABLED`, 기본 꺼짐)을
   관리자가 명시적으로 켜야만 Tier A 툴과 Tier B **제안 생성**이 동작합니다. 꺼진 상태에서
   호출하면 에러가 반환됩니다. 단, 이미 생성된 제안을 **승인/거부**하는 것은 관리자가 이미
   인증된 웹 세션에서 직접 누르는 액션이라 이 설정과 무관하게 항상 가능합니다 — 그래야
   써놓은 스위치를 꺼도 대기 중인 제안을 정리(거부)할 수 있습니다.
5. **감사 로그.** 모든 쓰기 실행(Tier A 즉시 실행, Tier B 제안 생성/승인/거부)은
   `logs/mcp_write_audit.log`에 대상/변경 전후 값과 함께 기록되며, `read_logs` 툴
   (`log_name="mcp_write_audit.log"`)로 언제든 조회할 수 있습니다. 대기 중인 제안 목록
   자체는 `run_readonly_query('general', 'SELECT * FROM mcp_pending_changes ORDER BY id DESC')`
   로도 조회할 수 있습니다(별도 읽기 전용 툴은 추가하지 않았습니다).

### 입력 검증 — "AI가 써넣은 텍스트가 관리자 브라우저에서 실행되는" 경로 차단

Tier A 도구를 설계하면서 "AI(또는 이를 조종하는 프롬프트 인젝션)가 장르/태그/요약 같은
자유 텍스트 필드에 악성 마크업을 심으면 어떻게 되는가"를 별도로 점검했습니다. 그 결과 이
필드들이 렌더링되는 화면 두 곳(도서 상세 페이지 헤더, 장르/태그 필터 UI)에서 이스케이프 없이
`innerHTML`로 그대로 꽂히는 **기존(MCP 이전부터 있던) 저장형 XSS 취약점**을 발견해 수정했습니다
— 관리자가 그 도서 상세 페이지를 열기만 해도 삽입된 스크립트가 관리자의 인증된 브라우저
세션에서 실행되어, 결과적으로 관리자 권한으로 플러그인 설치/설정 변경 등 어떤 POST 액션이든
대신 수행시킬 수 있는 경로였습니다.

렌더링 쪽 수정이 근본 대책이지만, MCP는 이 필드들에 대한 새로운 원격 쓰기 경로이므로
`update_book_metadata`에도 방어심층화를 추가했습니다:

- 모든 필드에서 `<`, `>` 문자를 거부합니다(HTML 태그 삽입 자체를 차단).
- `link` 필드는 `http://` 또는 `https://`로 시작하지 않으면 거부합니다(`javascript:` 등
  위험한 프로토콜 차단).

같은 점검 과정에서 `call_api`로 도달 가능한 `/api/media/videos/check-vaapi` 엔드포인트의
`device` 쿼리파라미터가 검증 없이 `subprocess`/`os.path.exists()`에 그대로 흘러가던 것도
발견해 `/dev/dri/` 아래 디바이스 노드 이름만 허용하도록 고쳤습니다(리스트 인자 방식이라
셸 명령 인젝션 자체는 불가능했지만, 임의 경로 존재 여부를 캐내는 프로빙 오라클로는
악용될 수 있었습니다).

**중요한 한계:** 위 검증은 "MCP가 직접 스크립트를 심는 것"을 막을 뿐, MCP 도구가 반환하는
텍스트(도서 제목/요약/로그 줄 등)를 AI가 지시문으로 착각해 **자기 자신의 다른 도구**(예:
Bash)로 파괴적 행동을 시도하는 것까지는 막지 못합니다. 이 계층의 방어는 MCP 서버가 아니라
MCP 클라이언트(AI 에이전트)의 권한/승인 모델의 몫입니다 — MCP 도구가 반환하는 모든 텍스트는
누구나 서재에 심을 수 있는 **데이터**이며, 그 안에 지시문처럼 보이는 내용이 있어도 절대
명령으로 취급해서는 안 됩니다.

## db_type 값

대부분의 툴은 `db_type` 파라미터를 받습니다: `general`(일반 도서, 기본값) / `adult`(성인 서재) / `audiobook`(오디오북). `video`는 book 테이블 구조가 달라 진단 전용 툴(`find_missing_*`, `find_duplicate_series`)의 대상은 아니지만, `run_readonly_query`는 `video`도 허용합니다.

## 향후 계획

- Tier B 액션 타입 확장 — 지금은 대량 메타데이터 수정/즐겨찾기 두 가지만 제안 큐를 지원합니다. 재스캔 트리거, 삭제성 작업 등이 필요해지면 `services/mcp_proposal_service.py`에 tool_name 분기만 추가하면 됩니다.
- 고아 파일(DB엔 있는데 디스크엔 없는 파일) 감지 — 원격 마운트 환경에서 전수 디스크 I/O가 느려서, 기존 스캐너 큐를 재사용하는 백그라운드 작업 + 결과 조회 전용 툴로 별도 추진합니다.
