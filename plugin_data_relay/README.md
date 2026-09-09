# Plugin Data Relay

BookOasis 플러그인 개발자가 웹에서 개발자 계정을 만들고(`/regi_user`), 그 계정으로 최대 5개의 커스텀 필드를 정의하면(`/register`) 해당 스키마에 맞는 SQLite 테이블이 자동 생성되고, 관리자 승인 후 간단한 REST API로 데이터를 저장/조회할 수 있는 범용 릴레이 서비스입니다. 게임 플러그인의 점수판(리더보드) 등 소규모 크로스유저 데이터 공유 용도에 적합합니다.

## 로컬 실행 방법
```bash
cd plugin_data_relay
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_SECRET_KEY=아무-랜덤-문자열
export ADMIN_PASSWORD=관리자-비밀번호
python app.py
```
`FLASK_SECRET_KEY`, `ADMIN_PASSWORD`는 기본값 없이 필수 환경변수입니다 (공개 저장소에 자격 증명을 하드코딩하지 않기 위함).

## API 개요

### 1. 개발자 계정 등록 — `POST /regi_user`
```json
{ "developer_id": "my_dev_id" }
```
응답의 `developer_secret`은 이 호출에서만 노출되며, 서버에는 해시로만 저장됩니다. 이후 `/register` 호출 시 이 `developer_id`+`developer_secret`으로 인증합니다.

### 2. 플러그인 필드 스키마 등록 — `POST /register`
```json
{
  "developer_id": "my_dev_id",
  "developer_secret": "...",
  "plugin_id": "my_game_plugin",
  "fields": [
    {"name": "score", "type": "INTEGER"},
    {"name": "nickname", "type": "TEXT"}
  ]
}
```
응답의 `plugin_secret`은 이 호출에서만 노출되며, 서버에는 해시로만 저장됩니다. 필드는 1~5개이며 `id`/`user_id`/`created_at`은 고정 컬럼과 충돌하므로 사용할 수 없습니다. 등록 후 스키마 변경은 지원하지 않습니다.

**등록만으로는 사용 불가**: 신규 등록된 플러그인은 `status='pending'` 상태이며, 관리자가 `/admin` 대시보드에서 승인(`approved`)하기 전까지는 아래 `verify`/`records` 계열 API가 모두 403을 반환합니다. 누구나 웹에서 developer_id/plugin_id를 선점할 수 있는 구조이므로, 실제 데이터 저장은 반드시 관리자 승인을 거치도록 막아둔 것입니다.

### 3. 최종 사용자(플레이어) 인증 — `POST /api/<plugin_id>/verify`
```json
{ "user_id": "player123", "secret_token": "클라이언트에서-생성한-32자리-랜덤값" }
```
최초 호출 시 자동 등록됩니다 (`sample_plugins/metadata/bo_relayss` 클라이언트 패턴과 동일).

### 4. 레코드 저장 — `POST /api/<plugin_id>/records`
```json
{ "user_id": "player123", "secret_token": "...", "values": {"score": 100, "nickname": "홍길동"} }
```
`values`에 등록되지 않은 필드명이 있으면 400 에러.

### 5. 레코드 조회 — `GET /api/<plugin_id>/records?user_id=...&secret_token=...&order_by=score&order_dir=desc&limit=10`
`order_by`는 등록된 필드명 또는 `id`/`created_at`만 허용됩니다 (리더보드 Top-N 조회에 사용).

### 6. 레코드 삭제 — `DELETE /api/<plugin_id>/records/<id>`
본인이 작성한 레코드만 삭제 가능합니다.

## Fly.io 배포 방법
```bash
cd plugin_data_relay
fly launch --copy-config --name bo-plugin-relay  # 최초 1회 (볼륨 생성 여부 확인)
fly secrets set FLASK_SECRET_KEY=$(openssl rand -hex 32) ADMIN_PASSWORD=원하는-비밀번호
fly deploy
```
`FLASK_SECRET_KEY`/`ADMIN_PASSWORD`는 절대 `fly.toml`의 `[env]`에 넣지 마세요 (평문으로 git에 커밋됨) — 반드시 `fly secrets set`으로 관리합니다.

## 관리자 대시보드
`/admin` — 등록된 플러그인 목록, 필드 스키마, 사용자/레코드 수를 모니터링합니다 (`ADMIN_PASSWORD`로 로그인).
