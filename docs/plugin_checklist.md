# 플러그인 작성 체크리스트

새 메타데이터/대시보드 플러그인을 추가할 때 이 항목만 확인하면 됩니다.

---

## 1. 위치와 이름

- `plugins/metadata/` 아래에 둡니다.
- 가능하면 폴더 기반으로 만듭니다.
- 폴더명, 파일명, 클래스명, `id`를 서로 맞춥니다.

예시:

- `plugins/metadata/my_plugin/my_plugin.py`
- `class MyPluginMetadataProvider(BaseMetadataProvider)`
- `id = "my_plugin"`

---

## 2. 반드시 상속할 것

- `BaseMetadataProvider`를 상속합니다.
- `search()`와 `apply()`는 반드시 구현합니다.

---

## 3. DB 접근 원칙

- 플러그인에서 `import database`를 직접 쓰지 않습니다.
- `self.get_db_gateway(db_type)`를 사용합니다.
- 설정값은 `self.get_plugin_config(db_type, default={})`로 읽습니다.

권장 메서드:

- `fetch_one()`
- `fetch_all()`
- `execute()`
- `execute_many()`
- `transaction()`

---

## 4. 대시보드 플러그인

대시보드에 보이게 하려면 아래를 구현합니다.

- `dashboard_widget`
- `get_dashboard_data()`

체크 항목:

- `get_dashboard_data()`는 `{'success': True, 'items': [...]}` 형태를 반환하는가
- `items` 안에 `metric` 카드와 일반 카드가 섞여도 문제없는가
- `limit` 인자를 무시하지 않는가

---

## 5. 컨텍스트 메뉴 플러그인

도서 컨텍스트 메뉴에 항목을 추가하려면 아래를 구현합니다.

- `get_context_menu_items()`
- `run_context_menu_action()`

체크 항목:

- `id`와 `label`이 비어 있지 않은가
- 반환값이 `success / error` 규격을 따르는가
- 필요하면 `open_url`을 반환하는가

---

## 6. 설정과 활성화

- `config_schema`가 필요한지 확인합니다.
- 설정 저장 키는 `PLUGIN_CONFIG_<id>`를 사용합니다.
- 활성화 키는 `PLUGIN_ENABLED_<id>`입니다.

체크 항목:

- 플러그인 활성화가 기본값으로 켜져 있는가
- 설정 JSON이 깨져도 실패하지 않는가

---

## 7. 자동 업데이트 계약 (플러그인 내부 선언)

- 자동 업데이트 규칙은 코어 하드코딩이 아니라 `update_manifest`로 선언합니다.
- 자동 업데이트 지원 대상이면 플러그인 루트 `VERSION` 파일에 `"plugin version"` 키를 둡니다.

체크 항목:

- `update_manifest.enabled = True` 인가
- `provider = "github-raw"` 인가
- `raw_base_url`가 실제 GitHub raw 경로와 일치하는가
- `files` 목록에 실제 배포 파일과 `VERSION`이 포함되어 있는가
- `version_key`를 `plugin version`으로 선언했는가
- 업데이트 게이트가 `현재 버전 < GitHub 버전`일 때만 통과하는가

---

## 8. 오류 예방

- import 에러가 없나 확인합니다.
- 클래스명과 파일명 매칭이 맞는지 확인합니다.
- `id` 중복이 없는지 확인합니다.
- 플러그인 폴더 안에 `__pycache__`를 직접 커밋하지 않습니다.

자주 발생하는 실패 사례:

- `ImportError`: 폴더명/파일명/클래스명 불일치로 로더 탐지 실패
- `id` 충돌: 다른 플러그인과 `id` 중복
- `config_schema` 타입/키 누락: 설정 UI 렌더링 실패
- `update_manifest` 오타: 샘플 업데이트 버튼 미노출 또는 업데이트 실패
- 웹훅 서명 검증 실패: `WEBHOOK_EVENT_SECRET` 불일치로 수신 서버 401/403
- EPUB/TXT 진행률 오해: `totalPages` nullable 케이스 미처리로 파서 오류

---

## 9. 최소 검증

플러그인 추가 후 아래 순서로 확인합니다.

1. 서버 재시작
2. `MetadataFactory.get_available_providers()`에 노출되는지 확인
3. 대시보드 위젯이면 `/api/media/dashboard/widgets` 응답 확인
4. 컨텍스트 메뉴면 `/api/media/context-menu/book/plugins` 응답 확인
5. 플러그인 데이터 호출이 500 없이 동작하는지 확인
6. (업데이트 지원 플러그인) `sample-update` 호출 시 404/버전 게이트 메시지가 의도대로 노출되는지 확인

---

## 10. 표준 이벤트 웹훅 검증 (book.new/read/finish)

커뮤니티 연동용 표준 이벤트 웹훅을 쓰는 경우 아래를 확인합니다.

- 환경변수 설정이 유효한가
	- `WEBHOOK_EVENT_ENDPOINT` 또는 `WEBHOOK_EVENT_ENDPOINTS`
	- `WEBHOOK_EVENT_TIMEOUT`, `WEBHOOK_EVENT_RETRY`
	- (사용 시) `WEBHOOK_EVENT_SECRET`
- `book.new`, `book.read`, `book.finish` 이벤트가 각각 발행되는가
- 최상위 키 `event`, `user`, `Account`, `Metadata` 구조가 유지되는가
- HMAC 검증을 켠 경우 `X-BookOasis-Signature` 검증이 통과하는가

포맷 제약 검증(중요):

- EPUB/TXT에서 `totalPages`가 `null`이어도 소비 측 로직이 정상 동작하는가
- EPUB/TXT 진행률은 페이지 수가 아니라 `Metadata.progress`(0~100) 기준으로 처리하는가
- `Metadata.currentLocation` 포맷별 파싱이 가능한가
	- EPUB: `href`/`cfi`/`spine` 문자열
	- TXT: `chunk:N`
	- PDF/ZIP/CBZ: `page:N`

---

## 11. CI 친화 고정 검증 시나리오

아래 순서를 그대로 자동화하면, 플러그인/웹훅 회귀를 빠르게 검출할 수 있습니다.

1. 서버 기동 후 `/api/media/dashboard/widgets`가 200 + JSON `success=true`인지 확인
2. 테스트 플러그인 활성화 후 `/api/media/metadata/plugins` 응답에서 대상 `id`가 노출되는지 확인
3. 테스트 도서 1권 스캔으로 `book.new` 이벤트 수신 여부 확인
4. 뷰어 진행률 저장 호출(`/api/media/progress`) 후 `book.read` 이벤트 수신 여부 확인
5. 진행률을 완독 전이 조건으로 업데이트 후 `book.finish` 이벤트 1회 수신 여부 확인
6. 웹훅 서명 사용 시 `X-BookOasis-Signature` HMAC 검증 통과 확인

기대 결과:

- 각 단계에서 HTTP 2xx 또는 문서화된 성공 응답만 허용
- `book.finish`는 동일 도서/사용자 조합에서 완료 전이 시점에만 1회 발행
- EPUB/TXT 도서에서도 이벤트 파싱이 실패하지 않아야 함 (`totalPages` nullable 허용)
