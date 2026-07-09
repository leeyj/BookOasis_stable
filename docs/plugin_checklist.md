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

## 7. 오류 예방

- import 에러가 없나 확인합니다.
- 클래스명과 파일명 매칭이 맞는지 확인합니다.
- `id` 중복이 없는지 확인합니다.
- 플러그인 폴더 안에 `__pycache__`를 직접 커밋하지 않습니다.

---

## 8. 최소 검증

플러그인 추가 후 아래 순서로 확인합니다.

1. 서버 재시작
2. `MetadataFactory.get_available_providers()`에 노출되는지 확인
3. 대시보드 위젯이면 `/api/media/dashboard/widgets` 응답 확인
4. 컨텍스트 메뉴면 `/api/media/context-menu/book/plugins` 응답 확인
5. 플러그인 데이터 호출이 500 없이 동작하는지 확인
