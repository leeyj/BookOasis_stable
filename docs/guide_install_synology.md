[English](guide_install_synology_en.md)

# Synology NAS에 설치하기 (Container Manager)

터미널이나 git 없이, NAS 화면에서 **설정 글 하나를 붙여넣는 것**으로 설치합니다. (15분 정도)

> **검증 범위**: 아래 compose 내용과 경로·권한 동작은 Docker(Ubuntu)에서 그대로 실행해 확인했습니다 (2026-11-03).
> DSM 화면의 메뉴 이름·순서는 Synology에서 직접 확인하지 못했습니다. 화면이 다르면 커뮤니티에 알려 주세요.

---

## 0. 먼저 알아둘 것: 경로가 두 개입니다

BookOasis는 NAS 안의 "작은 상자(컨테이너)"에서 돌아갑니다. 상자 안에서는 NAS 폴더가 **다른 이름**으로 보입니다.

| NAS에서 보이는 경로 | BookOasis(상자 안)에서 보이는 경로 |
|---|---|
| `/volume1/books` | `/data/books` |

이 연결은 아래 설정 글에서 한 줄로 정합니다. 나중에 BookOasis에서 카테고리를 만들 때는 **오른쪽(`/data/books`)** 을 적어야 합니다. 왼쪽 NAS 경로를 적으면 "서버에 존재하지 않거나 오타가 있습니다" 오류가 납니다 — 가장 흔한 실수입니다.

---

## 1. Container Manager 설치

**패키지 센터** → `Container Manager` 검색 → **설치**

---

## 2. 폴더 만들기

**File Station**에서 `docker` 공유 폴더 안에 아래 폴더를 만듭니다. (`docker` 공유 폴더는 Container Manager를 설치하면 생깁니다)

```
docker/
  bookoasis/
    db/
    covers/
    cache/
    tts_audio/
    plugins/
```

> Container Manager는 없는 폴더를 연결하려 하면 오류로 멈추는 경우가 있어, 미리 만들어 두는 것이 안전합니다.

내 책이 있는 폴더 경로도 확인해 두세요. File Station에서 책 폴더를 우클릭 → **속성** → 위치에 `/volume1/…`로 나옵니다.

---

## 3. 프로젝트 만들기 (설정 글 붙여넣기)

**Container Manager → 프로젝트 → 생성**

- 프로젝트 이름: `bookoasis`
- 경로: 2단계의 `docker/bookoasis`
- 원본: **docker-compose.yml 만들기**

아래 글을 통째로 붙여넣고, **표시된 두 곳만** 바꿉니다.

```yaml
services:
  bookoasis:
    image: ghcr.io/leeyj/bookoasis:stable
    container_name: bookoasis
    restart: unless-stopped
    stop_grace_period: 1m
    ports:
      - "5930:5930"
    environment:
      - SECRET_KEY=change-me-to-any-long-random-sentence-2026   # ① 아무 긴 문장으로 바꾸기
      - TZ=Asia/Seoul
      - REDIS_URL=redis://redis:6379/0
      # - PUID=1026   # (선택) 아래 "권한" 참고
      # - PGID=100
    volumes:
      - ./db:/app/db
      - ./covers:/app/covers
      - ./cache:/app/cache
      - ./tts_audio:/app/tts_audio
      - ./plugins:/app/plugins
      - /volume1/books:/data/books:ro   # ② 왼쪽만 내 책 폴더로 바꾸기
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    container_name: bookoasis_redis
    restart: unless-stopped
```

- **① SECRET_KEY**: 로그인 상태를 지키는 열쇠입니다. 영어·숫자로 된 아무 긴 문장이면 됩니다. 비워 두면 NAS를 재시작할 때마다 모두 로그아웃됩니다.
- **② 책 폴더**: 콜론(`:`) **왼쪽**만 내 NAS 경로로 바꿉니다. 오른쪽 `/data/books`와 끝의 `:ro`(읽기 전용)는 그대로 둡니다.
  책 폴더가 여러 개면 줄을 더 넣습니다:
  ```yaml
      - /volume1/만화:/data/comics:ro
      - /volume1/소설:/data/novels:ro
  ```

**다음** → 웹 포털 설정은 건너뛰고 → **완료**. 처음에는 이미지를 받느라 몇 분 걸립니다.

**이렇게 보이면 성공**: 컨테이너 목록에 `bookoasis`, `bookoasis_redis` 두 개가 **실행 중**.

---

## 4. 접속하고 비밀번호 바꾸기

브라우저에서 `http://NAS주소:5930` (예: `http://192.168.0.10:5930`)

- 처음 계정: `admin` / `admin`
- 로그인하면 **비밀번호 변경 화면이 먼저 나옵니다.** 바꾸기 전에는 다른 기능을 쓸 수 없습니다.

---

## 5. 첫 카테고리 만들기

**카테고리 추가** → 경로에 **`/data/books`** (3단계 ②의 오른쪽) → 저장

잠시 뒤 책이 나타나면 끝입니다. 🎉

---

## 권한 (PUID / PGID) — 선택

**설정 글을 그대로 쓰면 신경 쓰지 않아도 됩니다.** 기본값으로는 BookOasis가 NAS 폴더를 모두 읽을 수 있습니다.

BookOasis를 특정 NAS 사용자 권한으로만 돌리고 싶다면 `PUID`/`PGID` 줄의 `#`을 지우고 그 사용자의 번호를 적습니다.

- 번호 확인: **제어판 → 작업 스케줄러 → 생성 → 예약된 작업 → 사용자 정의 스크립트**에서 사용자를 고르고 명령에 `id` 입력 → 실행 결과(이메일 알림 또는 로그)의 `uid=…`, `gid=…`
  (SSH를 쓸 줄 안다면 `id 사용자이름`)
- **그 사용자에게 책 공유 폴더 읽기 권한이 꼭 있어야 합니다.** (제어판 → 공유 폴더 → 편집 → 권한)

> 권한이 없으면 **카테고리는 오류 없이 만들어지지만 책이 0권**으로 나옵니다. 화면에는 이유가 나오지 않고, 로그에만 `Permission denied: '/data/books'`가 남습니다. (직접 재현함) 이럴 땐 권한을 주거나 PUID/PGID 줄을 다시 `#`으로 막고 프로젝트를 재시작하세요.

---

## 업데이트 (화면 순서는 커뮤니티 확인 필요)

**Container Manager → 프로젝트 → bookoasis → 작업 → 빌드** (이미지를 새로 받아 다시 만듭니다). 또는 **이미지** 메뉴에서 `ghcr.io/leeyj/bookoasis`에 업데이트 표시가 있으면 업데이트 후 프로젝트를 다시 시작합니다.

데이터(`db`, `covers` 등)는 2단계 폴더에 있어서 업데이트해도 그대로 남습니다.

---

## 자주 막히는 곳

| 증상 | 원인 → 해결 |
|---|---|
| 카테고리 추가 때 "서버에 존재하지 않거나 오타가 있습니다" | NAS 경로(`/volume1/…`)를 적음 → **`/data/books`** 처럼 오른쪽 경로를 적기 |
| 카테고리는 생겼는데 0권 | PUID/PGID 사용자에게 책 폴더 읽기 권한 없음 → 위 "권한" |
| 프로젝트 만들 때 bind mount / 경로 오류 | 2단계 폴더가 없음, 또는 ② 왼쪽 NAS 경로 오타 |
| `5930` 포트가 이미 사용 중 | `ports:`를 `"5940:5930"`처럼 왼쪽만 바꾸고 `http://NAS주소:5940`으로 접속 |
| NAS 재시작 후 매번 로그아웃 | ① SECRET_KEY가 비었거나 매번 바뀜 → 고정된 문장 넣기 |
| 바깥(인터넷)에서 접속하고 싶다 | 공유기 포트 열기보다 Tailscale 또는 DSM 역방향 프록시 + HTTPS 권장 ([설치 가이드 4장](guide_installation.md)) |

구글 드라이브의 책을 연결하려면 [구글 드라이브 연결하기 (rclone)](guide_rclone_gdrive.md)를 보세요.

---

관련 문서: [오라클 무료 서버 설치](guide_install_oracle.md) · [구글 드라이브 연결 (rclone)](guide_rclone_gdrive.md) · [설치 가이드](guide_installation.md)
