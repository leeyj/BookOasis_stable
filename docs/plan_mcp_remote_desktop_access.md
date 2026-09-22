# Plan: BookOasis MCP 원격(Desktop) 접속

**상태: 보류 (구현 안 함, 계획만 기록).** 2026-09-22에 충동적으로 튀어나온 아이디어일 수 있어
시간을 두고 다시 검토하기로 함. 아래는 그 시점 세션에서 정리한 계획.

## 배경 / 동기
- 지금은 데스크탑에서 홈서버의 `tools/mcp_server.py`(로컬 stdio MCP 서버)를 쓰려면 매번 SSH 접속 필요
- "가끔 밖(카페·회사 등)에서도" 쓰고 싶다는 니즈 확인 → 진짜 원격(인터넷) 노출이 필요한 상황
- **재검토 시 먼저 물을 질문**: 이게 실제로 반복되는 불편이었는지, 아니면 그날의 충동이었는지.
  객관적으로 지금 SSH 방식이 보안상 더 낫고, "귀찮음"과 "인증 계층을 늘리는 리스크"를 저울질해야 함.

## 핵심 설계 결정 (재검토 시에도 유지 권장)
로컬(SSH stdio)과 원격(HTTPS) 인스턴스를 **완전히 분리**:
- 로컬: 기존 그대로, SSH+stdio, Tier A/B 쓰기 도구 포함 전체 권한 — 변경 없음
- 원격: 새 HTTPS 엔드포인트, **읽기 전용 도구만** 노출 (쓰기 도구는 코드 레벨에서 아예 미등록,
  `MCP_WRITE_ENABLED`와 무관). `run_readonly_query`(임의 SQL 추정)/`call_api`도 원격 프로필에서는
  제한 여부 재검토 필요.
- 이유: 원격 토큰이 SSH 키보다 유출 가능성이 높은 환경(카페 와이파이 등)에서 쓰이므로,
  유출돼도 피해 범위를 "조회"로 한정.

## 검토했던 대안들 (결론: 아래 순서로 폐기/채택)
1. ~~자체 OAuth 2.1 서버(DCR 포함) 직접 구현~~ — Claude Desktop 커스텀 커넥터 GUI가 OAuth 2.1 +
   동적 클라이언트 등록(DCR)을 강제하고 고정 헤더/Bearer 토큰 입력 필드가 없음이 확인됨
   (Claude Code CLI는 정적 bearer 지원하지만 **Desktop 앱은 미지원**, fallback 없음).
   구현 가능하지만 작업량이 큼(로그인 폼, 토큰 발급/갱신/폐기, DCR 엔드포인트 등).
2. **채택안 — `mcp-remote` npm 래퍼 사용**: Desktop이 로컬 stdio로 `npx mcp-remote <url> --header
   "Authorization:${AUTH_HEADER}"`를 실행하는 브리지 프로세스를 띄우고, 그 브리지가 원격 HTTPS
   MCP 서버로 고정 Bearer 토큰을 얹어 연결. Desktop 쪽엔 OAuth/DCR이 필요 없어지고, 서버 쪽도
   OAuthProvider 전체 대신 **고정 토큰 검증 미들웨어 몇 줄**로 충분해짐. 단, 스크린샷의
   "커스텀 커넥터 추가" GUI는 쓰지 않고 `claude_desktop_config.json`을 직접 편집해야 함.

## 채택안 기준 단계별 계획

### Phase 0 — 스파이크 (반나절)
로컬 포트에서 streamable-http + 고정 bearer 미들웨어를 띄워놓고, `mcp-remote`가 실제로
연결·인증까지 붙는지 먼저 검증. (Windows Desktop의 npx 인자 공백 이스케이프 버그 때문에
`"Authorization:${AUTH_HEADER}"`처럼 콜론 뒤 공백 없이 써야 함 — 알려진 워크어라운드.)

### Phase 1 — Transport 추가
- 기존 `tools/mcp_server.py`는 건드리지 않고 새 진입점 `tools/mcp_server_remote.py` 분리
  (읽기 전용 도구만 등록)
- `mcp.run(transport="streamable-http", host="127.0.0.1", port=<내부포트>)`로 루프백에만 바인딩,
  외부 노출은 nginx가 담당

### Phase 2 — 고정 토큰 인증 (경량화됨)
- `mcp` SDK의 TokenVerifier로 고정 Bearer 토큰 검증 (문자열 비교 수준)
- 토큰은 `.env`에만 저장 (저장소에 하드코딩 금지 원칙 준수)
- 원격 MCP 호출은 기존 audit log와 별도로 로그(IP 포함)
- 토큰 유출 시 즉시 무효화할 수 있는 킬스위치(.env 값 교체 + 재시작)
- (원한다면) 토큰을 프로세스 인자 대신 `--header-file`로 넘겨 같은 PC의 다른 사용자가
  프로세스 목록에서 못 보게

### Phase 3 — 네트워크 노출
- 신규 서브도메인 (예: `mcp.carls-dev.org`), 기존 bookoasis 홈페이지와 동일한 Cloudflare DNS
  패턴 재사용
- nginx reverse proxy → 내부 루프백 포트, 기존 TLS 구조 재사용
- Cloudflare 오렌지 클라우드(프록시)로 DDoS/TLS 앞단 방어 추가

### Phase 4 — 테스트 & 문서
- `mcp-remote` 브리지로 실제 Desktop 연결 테스트 (토큰 무효화 시나리오 포함)
- `docs/guide_mcp_server.md`/영문판에 "원격 접속(mcp-remote)" 절 추가, CHANGELOG 기록

## 재검토 시 먼저 확인할 것
- 지난 몇 주간 "SSH 접속 귀찮음"이 실제로 몇 번 발목을 잡았는지 (충동 여부 판단 근거)
- 그 시점 `mcp` SDK/`mcp-remote` 버전이 바뀌었는지 (2026-09-22 기준 mcp 2.2.0)
- 원격 프로필에 노출할 도구 목록 최종 확정 (`run_readonly_query`/`call_api` 포함 여부)

## 참고: 다른 오픈소스 도서관리 MCP는 어떻게 하나 (2026-09-22 조사)
결론: **비교 대상이 될 만한 도서관리 MCP들은 전부 로컬 stdio 전용이고, 원격 노출을 서버 자체
기능으로 만든 사례가 없음.** 원격이 필요하면 서버가 아니라 클라이언트 쪽에서 `mcp-remote` 같은
범용 브리지를 얹는 게 커뮤니티 관행 — 저 문서의 "채택안"과 일치함.

- [`trieloff/calibre-mcp`](https://github.com/trieloff/calibre-mcp) — Calibre 서재 검색/독서용
  MCP, `calibredb` CLI 기반, stdio only
- [`ajtudela/calibre_mcp_server`](https://github.com/ajtudela/calibre_mcp_server) — 마찬가지로
  Calibre e-book 서재용 MCP, stdio 전용

일반 가이드라인도 같은 방향:
> "개인용 도구를 본인 기기에서만 쓴다면 호스팅은 비용·복잡도만 늘릴 뿐 이득이 없다 — 로컬이
> 이긴다. 본인 노트북 하나를 넘어 다른 사람/기기가 접근해야 하는 순간 원격으로 넘어가는 것."
> ([Railway](https://docs.railway.com/guides/local-vs-remote-mcp-servers))
>
> "로컬 stdio는 신뢰된 사용자 1명·기기 1대에 적합. 원격 셀프호스팅은 팀이 인프라 통제권까지
> 필요할 때." ([mcpmanager.ai](https://mcpmanager.ai/blog/remote-vs-local-mcp-servers/))

**시사점**: "가끔 밖에서" 수준의 니즈는 이 임계값(여러 기기/여러 사람)에 아직 못 미칠 수 있음.
재검토 시 "정말 여러 기기·상황에서 반복적으로 필요한가"부터 먼저 자문할 것 — 조급하게 서두를
객관적 이유는 없다.
