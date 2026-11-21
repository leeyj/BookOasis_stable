# BookOasis (media_server) – 작업 규칙

공개 저장소(AGPLv3)다. 이 파일은 AI 코딩 도구와 기여자가 공통으로 따르는 규칙을 적는다.

## 보안

- 토큰, 비밀번호, API 키, 개인 경로를 코드·문서·테스트·커밋 메시지에 넣지 않는다. 예시에는 가짜 값(`example.invalid`, `0000…`)을 쓴다.
- 대화나 붙여 넣은 로그에 토큰이 보이면 그 값을 저장소에 옮기지 말고 사용자에게 알린다(특히 `eyJ` 로 시작하는 JWT).
- 이 서버는 홈 자동화(Home Assistant, MQTT)와 통신하지 않는다. 그 자격 증명이나 설정을 추가하지 않고, 이 저장소 밖의 홈 자동화 프로젝트 파일을 읽거나 고치지 않는다.
- 커밋 전 시크릿 스캔: `pip install pre-commit && pre-commit install` (규칙은 `.gitleaks.toml`).
- Claude 권한 설정은 `.claude/settings.example.json` 샘플만 커밋한다. 실제 경로가 든 설정은 `.claude/settings.local.json`(커밋하지 않음)에 둔다.
- 배포 스크립트(`deploy.py`, `test_deploy.py`)는 도움말을 보려고도 실행하지 않는다. 실행하면 바로 배포된다.

## 구조

- 진입점 `core.py`, 라우트 `api/`, 서비스 `services/`, DB 접근 `repositories/sqlite/` 와 `repositories/mariadb/`(두 엔진을 함께 고친다).
- 코어는 뷰어·스캔·카테고리·OPDS·진행 동기화 같은 기반만 맡고, 나머지는 플러그인(`plugins/`, `plugin_framework/`)으로 둔다.
- 남이 만든 이미지는 `utils.safe_image.open_image` 로 연다(`Image.open` 직접 사용 금지, 테스트가 검사한다).
- e-paper 리더 기능: 명세 `docs/device-api.md`, 피드 `api/opds_epaper.py`, 캐시 `services/epaper_service.py`, 변환기 `services/epaper/`. 변환기는 독립 모듈이라 DB·설정·Flask를 모르고, 코어에서는 `services/epaper_service.py` 만 변환기를 부른다. 변환 결과가 바뀌는 수정은 프로필 버전을 올린다.

## 테스트

- `.venv` 의 Python으로 `python -m pytest tests` (Python 3.10 호환 문법을 유지한다: f-string 식 안에 백슬래시 금지 등).
- 프런트 테스트는 `tests/*.mjs` (node).

## 버전과 변경 기록

- `VERSION` 의 `"dashboard"` 줄이 앱 버전이다. 규칙은 그 파일의 주석에 있다(각 자리 0~9).
- `CHANGELOG.md` 는 항목마다 한 줄, 한국어 | 영어.
