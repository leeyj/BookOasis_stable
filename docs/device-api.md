# e-paper 리더 기기 API (v1)

BookOasis 서버가 e-paper 리더(처음 대상은 reTerminal 800×480, ESP32-S3)에 제공하는 기능의 명세다. 이 문서는 서버 저장소가 관리한다. 펌웨어 쪽은 읽기만 한다. 예시의 계정, 주소, 해시는 모두 가짜 값이다.

- 서버 버전: 3.2.0부터(여러 기기 프로필은 3.2.1부터)
- 변환 프로필: `v1`(reTerminal, 기본), `x4`, `x3`, `gray-low`, `gray-hd`, `color-hd`(§5)
- 주소의 `v1`(`/opds-epaper/v1`)은 **피드 API 버전**이다. 프로필 id `v1` 과는 글자만 같은 별개 값이다. 프로필이 늘거나 바뀌어도 주소는 그대로이고, 피드의 요청·응답 형식이 바뀔 때만 `v2` 를 낸다.
- 관련 코드: `api/opds_epaper.py`(피드·다운로드·업로드), `services/epaper_service.py`(캐시), `services/epaper/`(변환기, 프로필 `profile.py`, 모델 표 `devices.py`), `services/kosync_service.py`(진행 동기화)

## 1. 개요

| 기능 | 경로 | 인증 |
| --- | --- | --- |
| 기기용 OPDS 피드 | `/opds-epaper/v1` 아래 | HTTP Basic (BookOasis 계정) |
| 변환본 다운로드 | `/opds-epaper/v1/book/<id>.epub` | Basic 또는 피드가 붙인 서명 토큰 |
| 피드 표지 | `/opds-epaper/v1/cover/<id>.jpg` | Basic 또는 서명 토큰 |
| 로컬 EPUB 업로드·변환 | `/opds-epaper/v1/uploads` 아래 | Basic + 업로드 권한 |
| 진행 동기화 (KOReader kosync 호환) | `/kosync` 아래 | `x-auth-user` / `x-auth-key` |

표준 피드 `/opds` 와 앱 피드 `/app-opds` 는 이 기능과 무관하다. 두 피드는 원본 파일을 그대로 보내고, 변환은 일어나지 않는다.

변환은 기기 피드에서 받기 링크를 요청할 때와 웹 화면의 책 메뉴 "기기용 받기"(`/api/media/books/<id>/epaper`, 로그인 세션 전용, 기기 API 아님)를 누를 때만, 그 책 한 권에 대해 일어난다. 미리 일괄 변환하지 않는다. 한 번 만든 변환본은 캐시에서 다시 쓴다. 웹 화면의 다운로드 버튼은 늘 원본을 보낸다.

## 2. 계정과 권한

- **피드·다운로드 계정**: 보통의 BookOasis 사용자 계정이다. 관리자가 기기 전용 계정을 따로 만들어 두는 것을 권장한다. 카테고리 권한(사용자 관리의 카테고리 접근 설정)이 피드 전체에 적용된다. 권한 설정이 없는 계정은 모든 카테고리를 본다. 책 받기에는 웹 다운로드와 같은 검사가 더 붙는다(3.2.2부터): 다운로드 권한이 없거나, 책 등급이 계정의 열람 등급보다 높으면 `403` 이다. 목록에는 웹 그리드처럼 그대로 보인다. 관리자는 검사하지 않는다.
- **피드 기기 설정**: 피드·피드 표지·업로드 변환의 프로필은 그 계정의 사용자 설정 "피드 기기"(`EPAPER_FEED_DEVICE`, 웹 → 설정 → 내 설정 → e-paper 리더)를 따른다. 설정이 없으면 `v1` 이다. 기기 전용 계정을 쓰면 **그 계정으로 웹에 로그인해** 피드 기기를 고른다(KOReader 사용자도 같다). 한 계정으로 피드 기기를 두 대 이상 쓰면 기기마다 계정을 나눈다. 관리자 전역값은 없다(사용자 값만 쓴다).
- **업로드 권한**: 설정 `EPAPER_UPLOAD_USERS`(쉼표로 구분한 사용자 이름)에 든 계정만 업로드 API를 쓸 수 있다. 비어 있으면 아무도 쓸 수 없다.
- **진행 동기화 계정**: kosync는 읽는 사람 본인 계정의 동기화 비밀번호로 접속한다. 진행 기록이 사용자별이라, 아이패드 KOReader와 같은 계정이어야 기록이 이어진다.
- **기기를 잃어버렸을 때**: 기기 전용 계정의 비밀번호와, 본인 계정의 동기화 비밀번호(웹 계정 메뉴 → KOReader 동기화)를 바꾸면 기기의 접근이 끊긴다. BookOasis 로그인 비밀번호는 기기에 저장되지 않는다.

Basic 인증 결과는 서버에서 5분 동안 캐시된다. 기기가 첫 요청을 인증 없이 보내면 서버는 `401`과 `WWW-Authenticate: Basic realm="BookOasis e-paper"` 를 돌려준다. 이것은 정상 흐름이다.

## 3. 기기용 OPDS 피드 `/opds-epaper/v1`

Atom XML(OPDS 1.2)이다. 일반(general) 도서관의 EPUB과 TXT만 보인다. 만화, PDF, 성인 도서관은 나오지 않는다.

### 3.1 경로

| 경로 | 종류 | 내용 |
| --- | --- | --- |
| `/opds-epaper/v1` | navigation | 신규 추가, 최근 읽은 책, EPUB/TXT가 있는 카테고리 목록(최대 40개) |
| `/opds-epaper/v1/library/<lib_id>?page=N` | navigation | 카테고리 안의 시리즈 목록. 항목 summary는 `N권` |
| `/opds-epaper/v1/library/<lib_id>/series?name=<시리즈>&page=N` | acquisition | 시리즈의 책 목록. 시리즈가 없는 책은 `name=-` |
| `/opds-epaper/v1/recent?page=N` | acquisition | 최근 추가된 책 (최대 5쪽) |
| `/opds-epaper/v1/reading?page=N` | acquisition | 이 계정이 최근 읽은 책 (최대 5쪽) |
| `/opds-epaper/v1/search` | OpenSearch 설명 | 인증 없이 응답한다 |
| `/opds-epaper/v1/search?q=<검색어>&page=N` | acquisition | 제목·시리즈·저자 검색(공백으로 나눈 단어 AND) |

### 3.2 페이지 나눔

- 모든 목록은 한 페이지에 **40항목**이다. 기기는 한 페이지에 62항목까지만 담을 수 있으므로 이 값은 그보다 작게 잡았다.
- 다음 페이지가 있으면 피드에 `<link rel="next" href="…?page=N+1"/>` 가 붙는다. 마지막 페이지에는 없다.
- `page` 는 1부터 센다. 피드의 모든 링크는 절대 주소다(`https://<서버>/opds-epaper/v1/…`).
- 하위 목록에는 `rel="up"`, 모든 피드에는 `rel="start"` 와 `rel="search"` 가 있다.

### 3.3 책 항목

```xml
<entry>
  <title>첫 권 시작</title>
  <id>urn:bookoasis:epaper:book:general:1234</id>
  <updated>2026-11-21T00:00:00Z</updated>
  <author><name>저자 이름</name></author>
  <summary>짧은 설명…</summary>
  <link rel="http://opds-spec.org/acquisition"
        href="https://example.invalid/opds-epaper/v1/book/1234.epub?token=SIG:EXPIRES:UID"
        type="application/epub+zip"/>
  <link rel="http://opds-spec.org/image"
        href="https://example.invalid/opds-epaper/v1/cover/1234.jpg?token=SIG:EXPIRES:UID" type="image/jpeg"/>
  <link rel="http://opds-spec.org/image/thumbnail" href="(위와 같음)" type="image/jpeg"/>
</entry>
```

- 받기 링크의 type은 TXT 원본을 포함해 **모두 `application/epub+zip`** 이다. 링크는 변환본을 가리킨다.
- **제목과 저자**: FAT32 파일 이름에 쓸 수 없는 문자(`\ / : * ? " < > |`, 제어 문자)를 공백으로 바꾸고, 공백을 하나로 줄이며, 앞뒤의 점과 공백을 지운다. 제목은 80자, 저자는 40자까지다. 기기는 이 값으로 파일 이름을 만든다.
- **summary**: HTML 태그를 지우고 200자까지 자른다(넘치면 끝에 `…`). 설명이 없으면 항목에 넣지 않는다.
- **표지**: 그레이스케일 베이스라인 JPEG이고 긴 변은 480px 이하다(원본 표지가 작으면 키우지 않는다, 지금은 모든 프로필이 같은 값). 표지가 없는 책은 이미지 링크가 없다. 표지 응답은 `Cache-Control: private, max-age=86400` 이라 피드 기기를 바꿔도 기기에 남은 표지는 최대 하루 그대로일 수 있다.
- **서명 토큰**: `token` 값은 1시간 동안 유효하다. 토큰이 있는 링크는 Basic 인증 없이도 받을 수 있다. 피드를 다시 받으면 새 토큰이 붙는다.
- 루트와 시리즈 목록 피드는 사용자별로 5분 동안 캐시된다. 책 목록 피드는 캐시되지 않는다(토큰이 매번 새로 붙는다).

## 4. 변환본 다운로드 `/opds-epaper/v1/book/<id>.epub`

### 4.1 동작

1. 캐시에 그 책의 변환본(요청한 계정의 피드 기기 프로필, TXT는 늘 `v1`)이 있고 원본이 바뀌지 않았으면(크기·수정 시각이 같으면) 바로 보낸다.
2. 없으면 변환을 시작하고 **최대 45초**(설정 `EPAPER_CONVERT_TIMEOUT_SEC`) 기다린다. 그 안에 끝나면 결과를 보낸다.
3. 45초 안에 끝나지 않으면 `503` 으로 답한다. 변환은 서버에서 계속된다. 다시 요청했을 때 끝나 있으면 캐시에서 바로 보낸다.
4. 같은 책을 여러 번 동시에 요청해도 변환은 한 번만 한다.

기기의 HTTP 소켓 타임아웃(60초)보다 짧게 잡기 위해 상한을 45초로 두었다. 원격 드라이브(rclone 등)에 있는 큰 책은 원본을 읽는 데만 시간이 걸릴 수 있다.

### 4.2 응답

| 상태 | 의미 | 본문 / 헤더 |
| --- | --- | --- |
| `200` | 변환본 | `Content-Type: application/epub+zip`, `Content-Length`, `X-Epaper-Profile: <프로필 id>`, `X-Epaper-Digest: <partial MD5>` |
| `401` | 인증 없음·실패 | `WWW-Authenticate: Basic …` |
| `403` | 다운로드 권한 없음, 열람 등급 초과 (3.2.2부터) | 텍스트 |
| `429` | 같은 IP에서 5분 안에 인증을 10번 틀림 → 5분간 거부 (3.2.2부터, kosync도 같음) | 텍스트, `Retry-After` |
| `404` | 책이 없음, EPUB/TXT가 아님, 카테고리 권한 없음 | 텍스트 |
| `422` | 변환할 수 없는 책(DRM, 손상된 ZIP, OPF 없음 등) | 텍스트 `이 책은 변환할 수 없습니다. (사유)` |
| `503` | 변환 중 | 텍스트 `변환 중입니다. 잠시 후 다시 받아 주세요.`, `Retry-After: 30` |

오류 본문은 모두 `text/plain; charset=utf-8` 한 줄이다. 변환에 실패한 책은 10분 동안 다시 변환하지 않고 같은 `422` 를 돌려준다. 원본 파일이 바뀌면 바로 다시 시도한다.

`X-Epaper-Digest` 는 KOReader 방식 partial MD5(§6.2)다. 기기가 파일에서 계산한 값과 같다.

`X-Epaper-Profile` 은 **실제 변환에 쓴 프로필**이다. 피드 기기 설정이 없으면 `v1`, TXT 원본은 피드 기기와 상관없이 늘 `v1`(§5.7)이다. 기기는 `v1` 이 아닌 값을 받을 수 있다.

## 5. 변환 프로필

같은 원본에 같은 프로필을 적용하면 **바이트 단위로 같은 파일**이 나온다(§5.6). 프로필은 기기 모델이 아니라 화면 등급이다. 수치는 `services/epaper/profile.py` 의 `Profile` 객체에 있고, 사용자가 고르는 기기 모델 → 프로필 표는 `services/epaper/devices.py` 에 있다(추가 방법: `docs/epaper-devices.md`).

| 프로필 id | 그림 상자(긴 변×짧은 변) | 본문 그림 | 실기기 확인 | 주 대상 |
| --- | --- | --- | --- | --- |
| `v1` | 800×480 | 2색 디더링 PNG(1비트) | 됨 | Seeed reTerminal |
| `x4` | 800×480 | 2색 디더링 PNG(1비트) | 안 됨 | Xteink X4 (처음 값은 `v1` 과 같다) |
| `x3` | 792×528 | 2색 디더링 PNG(1비트) | 안 됨 | Xteink X3 |
| `gray-low` | 1024×758 | 회색 JPEG q80 | 안 됨 | 화면 짧은 변 758px 이하 기기(Kobo Nia 등) |
| `gray-hd` | 1680×1264 | 회색 JPEG q80 | 안 됨 | 짧은 변이 758px보다 큰 흑백 기기(Kobo Clara·Libra·Sage 등) |
| `color-hd` | 1680×1264 | 컬러 JPEG q80 | 안 됨 | 컬러 화면(Kobo Libra Colour 등), Kindle(Send to Kindle) |

**바뀌는 규칙**
- 한 프로필의 값을 고치면 **그 프로필의 revision**(시작값 1)을 올린다. id는 바꾸지 않는다. 캐시에서 그 프로필의 변환본만 다시 만든다.
- 새 id는 화면 등급 자체가 새로 필요할 때만 만든다(새 저사양 해상도, 짧은 변 758px 이하 컬러 등). id는 OPF 표식·`X-Epaper-Profile`·캐시 키로 공개되므로 영구다. 문자는 소문자·숫자·`-` 만 쓴다(점 금지, `local-` 접두사는 예약).
- 모든 프로필의 결과가 바뀌는 변환기 수정(정규화 등)은 전역 변환기 리비전(`CONVERTER_REVISION`, 현재 3)을 올린다. TXT 결과가 바뀌는 수정도 이 값을 올린다(TXT는 프로필 revision을 보지 않는다).
- 어느 경우든 새 digest가 같은 책으로 등록되므로 EPUB의 진행 기록은 이어진다(§6.3). 주소(`/opds-epaper/v1`)는 바뀌지 않는다.

### 5.1 구조 보존 (EPUB 원본)

kosync 위치(xpointer, 예: `/body/DocFragment[12]/body/div/p[34]/text().5`)를 아이패드의 원본 EPUB과 기기의 변환본에서 똑같이 쓰기 위한 규칙이다.

- spine 항목의 수와 순서를 바꾸지 않는다. 챕터를 나누거나 합치지 않는다.
- XHTML 문서의 요소를 더하거나 빼지 않는다. 요소의 순서, 중첩, 텍스트 노드도 그대로다. 바뀌는 것은 속성(`style`, 그림 경로)과 `<head>` 안 `<style>` 의 내용뿐이다.
- HTML 이름 엔티티(`&nbsp;`, `&hellip;` 등)는 같은 문자로 바뀐다. 파서가 엔티티를 풀어 읽는 결과와 같다.
- 문서 인코딩은 UTF-8로 통일된다(XML 선언 포함).
- 목차 문서(nav, ncx)를 새로 만드는 경우에도 spine에는 넣지 않는다. 따라서 `DocFragment` 번호가 바뀌지 않는다.
- 예외: BookOasis 펌웨어 프로필(`v1`, `x4`, `x3`)은 텍스트에서 RLM류와 IVS를 지운다(§5.4). 요소는 그대로라 위치는 같은 문단을 가리키고, 그 문단 안의 글자 위치(`text().N`)만 지운 글자 수만큼 앞당겨진다.

**깨진 XHTML**: XML로 읽을 수 없는 문서는 libxml2의 복구 결과로 저장하고, 변환 보고서(`repaired_documents`)와 서버 로그에 남긴다. KOReader(crengine)가 같은 문서를 복구한 결과와 다를 수 있다. 그런 문서 안에서는 원본과 변환본의 위치가 어긋날 수 있다.

### 5.2 그림

- 대상: manifest의 JPEG, PNG, GIF, WEBP, BMP(표지 포함). 그 밖의 형식(SVG 등)과 읽을 수 없는 그림은 그대로 둔다.
- 방향에 맞춰 프로필의 그림 상자(§5 표) 안에 들어가게 줄인다. 작은 그림은 키우지 않는다.
- 투명한 부분은 흰 바탕과 합치고, 애니메이션은 첫 장만 쓴다.
- **PNG 프로필**(`v1`, `x4`, `x3`): Floyd–Steinberg 디더링으로 **2색(검정 0, 흰색 255)** 으로 만들고, 1비트 그레이스케일 PNG로 저장한다. 기기는 본문과 같은 1비트 갱신으로 그림을 그린다. (프로필의 `gray_levels` 를 4단계나 16단계로 두면 2비트·4비트 팔레트 PNG가 된다.) PNG가 아니던 그림은 확장자를 `.png` 로 바꾼다.
- **JPEG 프로필**(`gray-low`, `gray-hd`, `color-hd`): 디더링 없이 베이스라인 JPEG(q80)로 저장한다. `gray-*` 는 회색(8비트), `color-hd` 는 컬러다. 이미 상자 안에 드는 JPEG도 늘 다시 인코딩한다(CMYK·EXIF 방향·프로그레시브를 통일). JPEG이 아니던 그림은 확장자를 `.jpg` 로 바꾸고(`.jpeg` 는 그대로), `media-type` 은 `image/jpeg` 다.
- 이름이 바뀐 그림은 manifest와 문서 안의 참조(`img@src`, SVG `image@href` 등)를 함께 고친다. 요소는 그대로다(§5.1).
- 크기 참고: JPEG 프로필 변환본은 1비트 PNG 변환본보다 3~6배 크다(삽화 20장 소설 0.8MB → 2.6~4.9MB).

### 5.3 CSS

허용 목록에 있는 것만 남긴다. 스타일시트 파일, `<style>`, `style` 속성 모두 같은 규칙이다.

| 남는 속성 | 허용 값 |
| --- | --- |
| `text-align` | left, right, center, justify, start, end |
| `font-weight` | bold, bolder, normal, lighter, 100~900 |
| `font-style` | italic, oblique, normal |
| `text-decoration` | underline, line-through, overline, none |
| `font-size` | em, rem, % 또는 smaller, larger, small, medium, large, x-small, x-large |
| `text-indent` | em, rem, %, 0 |
| `vertical-align` | super, sub, baseline |
| `display` | none, block, inline |
| `page-break-before/after`, `break-before/after` | always/page, avoid, auto |

- 빠지는 것: 모든 at-rule(`@font-face`, `@media`, `@import`, `@page` …), 폰트 지정, 고정 크기(px, pt 등), 여백(margin, padding), float, position, 크기, 색, 배경, 테두리, 줄 간격, `!important`.
- 선택자는 단순한 것만 남는다: `p`, `.cls`, `p.cls`, `*`. 자손·자식·속성·가상 클래스 선택자가 든 규칙은 빠진다.
- 결과 스타일시트는 고정된 형식으로 다시 쓴다: `선택자 { 속성: 값; … }` 한 줄에 규칙 하나.

### 5.4 폰트

포함 폰트(ttf, otf, woff, woff2, eot, ttc)는 모두 지운다. 기기는 자기 폰트로 그린다. 아래 두 가지는 **BookOasis 펌웨어 프로필(`v1`, `x4`, `x3`)과 TXT에만** 적용된다. 다른 기기는 자기 폰트와 렌더러를 쓰므로 적용하지 않는다.

**글자 경고**: 기준은 펌웨어 기기 폰트(cpfont)의 실제 글자 범위 `services/epaper/device_fonts.json` 이다(펌웨어 저장소 `fonts/device-font-coverage.json` 사본). 기본 폰트(`BookOasisBatangCP`)를 포함해 폰트 5개 모두 KS X 1001 전체(한글·한자·기호·가나·그리스·키릴)와 기본 라틴이 들어 있다. 원본 폰트에 없는 몇 글자(예: ⑳€✔✓)는 예외다. 범위 밖의 글자는 기기에서 □로 보인다. 공백, 폭 0 문자, BOM은 세지 않는다.
- 변환 보고서 `glyphs`: 기본 폰트 기준 수(`missing_chars`, `missing_distinct`, `missing_sample`), 폰트별 수(`fonts`), □가 되는 첫 몇 곳(`locations`: 문서 경로 또는 TXT 섹션 이름과 앞뒤 글자).
- 기본 폰트에서 빠지는 글자가 본문 글자의 0.1%를 넘거나 30종 이상이면 서버 로그에 경고가 남는다(변환은 계속된다).
- 웹 "기기용 받기"는 웹 받기 기기가 펌웨어 기기이고 빠지는 글자가 있으면 응답 헤더 `X-Epaper-Glyphs`(퍼센트 인코딩한 JSON: `font`, `missing`, `kinds`, `sample`, 덜 빠지는 폰트 `better`)를 붙이고, 받기 완료 안내에 보여 준다.
- 기기 폰트를 다시 만들면 이 파일만 바꾼다. 변환 결과는 바뀌지 않으므로 revision은 올리지 않는다.

**보이지 않는 문자**: 기기 폰트가 폭 0 문자(ZWSP·ZWJ·LRM·변형 선택자 등)를 이미 빈 글리프로 처리하므로, 서버는 두 가지만 텍스트에서 지운다. 다른 글자로 바꾸지는 않는다(서버는 기기에서 고른 폰트를 모르고, 바꾸면 원문이 사라진다).
- RLM(U+200F), RLE(U+202B), RLO(U+202E), RLI(U+2067): 기기의 양방향 처리가 줄 전체를 오른쪽→왼쪽으로 뒤집는다. 히브리어·아랍어 등 오른쪽→왼쪽 글자가 있는 문단(TXT는 줄)은 그대로 둔다.
- IVS(U+E0100~E01EF, 한자 이체자 선택자): 기기 폰트에 없어 앞 한자 뒤에 □로 붙는다. 지우면 기본 한자 모양으로 보인다.
- 지운 수는 변환 보고서 `invisible_removed` 에 남는다. EPUB에서는 요소를 바꾸지 않는다(§5.1 예외 참고).

### 5.5 목차와 OPF

- ncx가 없으면 만든다. 기존 nav가 있으면 nav에서, 없으면 각 문서의 첫 제목(h1~h3, title)에서 만든다. EPUB3에 nav가 없으면 nav도 같은 방법으로 만든다. 이미 있는 목차는 그대로 둔다.
- OPF에 `<meta name="mediaserver:profile" content="<프로필 id>"/>` 가 들어간다(예: `v1`, `gray-hd`). TXT 원본은 늘 `v1`.
- 식별자(`dc:identifier`)는 원본 값을 그대로 쓴다. EPUB3 원본에 `dcterms:modified` 가 없으면 고정 값 `2000-01-01T00:00:00Z` 를 넣는다.
- `META-INF/encryption.xml` 에 폰트 난독화가 아닌 암호화가 있거나 `rights.xml` 이 있으면 DRM 책으로 보고 변환하지 않는다(`422`).

### 5.6 결정적 변환

- ZIP 엔트리 순서: `mimetype`(무압축) → `META-INF/container.xml` → 나머지는 이름순. 모든 엔트리의 시각은 1980-01-01 00:00:00, 권한·OS 필드도 고정이다.
- 생성 시각, 무작위 UUID, 환경에 따라 달라지는 값을 쓰지 않는다. TXT 변환본의 식별자는 원본의 SHA-256에서 만든다(`urn:sha256:…`).
- 같은 서버 환경(Python zlib, Pillow 버전)에서 바이트가 같다. 서버의 라이브러리 버전이 바뀌면 바이트가 달라질 수 있다. 그래도 새 digest가 같은 책으로 등록되므로(§6.3) 진행 기록은 이어진다.

### 5.7 TXT → EPUB

- 인코딩 판별 순서: UTF-8 BOM → UTF-16 BOM → BOM 없는 UTF-16(NUL 분포나 글자 분포로 판단) → UTF-8 → EUC-KR/CP949 → CP949(깨진 바이트는 대체 문자로 바꾸고 경고).
- 줄바꿈을 LF로 통일하고, 빈 줄이 아닌 줄 하나가 `<p>` 하나가 된다.
- RLM류와 IVS를 지운다(§5.4). TXT는 프로필과 무관한 한 벌이라 모든 기기에 적용된다.
- 챕터 제목: 50자 이하이고 따옴표·물음표·느낌표가 없는 줄 중 `제1장`, `1화`, `3편`, `Chapter 1`, `第1章`, `프롤로그`, `에필로그`, `서막`, `서장`, `종장`, `외전`, `후기` 형태.
  - 다음 제목까지 300자가 안 되는 제목은 본문 앞 목차로 보고 제목으로 쓰지 않는다.
  - 번호가 있는 제목은 번호가 계속 커지는 가장 긴 열만 쓴다(목차, 본문 속 "1화" 같은 오탐을 거른다).
  - 제목을 2개 이상 찾으면 제목마다 XHTML 하나다. 첫 제목 앞의 글은 책 제목으로 된 첫 섹션이 된다.
- 제목을 못 찾았거나 한 챕터가 20,000자를 넘으면 문단 경계에서 20,000자 안팎으로 나눈다(`제목 (2)` 처럼 번호가 붙는다). 20,000은 프로필 값이 아닌 공통 상수다.
- 결과는 EPUB3(nav + ncx)이고 §5.6 규칙을 따른다. TXT 원본에는 xpointer가 없으므로 §5.1 구조 보존 규칙과는 상관이 없다.
- **TXT 변환은 프로필과 무관하다.** 피드 기기·웹 받기 기기와 상관없이 늘 같은 바이트(OPF 표식 `v1`, `X-Epaper-Profile: v1`)이고 캐시도 `v1` 한 벌이다. 그래서 기기 설정을 바꿔도 TXT 책의 digest와 진행 기록은 그대로다.

## 6. 진행 동기화 (kosync)

### 6.1 접속

KOReader 진행 동기화 플러그인과 같은 API다. 서버 주소는 `https://<서버>/kosync`, 문서 식별 방식은 **바이너리(partial MD5)** 이다.

| 요청 | 설명 |
| --- | --- |
| `GET /kosync/users/auth` | `x-auth-user`, `x-auth-key`(동기화 비밀번호의 MD5 소문자 16진수) 확인 |
| `PUT /kosync/syncs/progress` | `{document, progress, percentage, device, device_id}` 저장. 응답 `{document, timestamp}` |
| `GET /kosync/syncs/progress/<document>` | 기록 조회. 없으면 `{}` |

### 6.2 문서 식별

KOReader `util.partialMD5` 와 같다. 파일의 오프셋 0, 1024, 4096, 16384, …, `1024 << 2i`(i = 0..10)에서 1KB씩 읽어 이어 붙인 뒤 MD5를 구한다. 파일 끝을 지나면 거기서 멈춘다. 변환본의 값은 다운로드 응답 헤더 `X-Epaper-Digest` 와 같다.

### 6.3 같은 책의 여러 문서

- 서버는 변환본을 만들 때와 내려줄 때 그 digest를 원본 책과 같은 book_id로 등록한다. 표준 `/opds` 로 원본을 받으면 원본 digest도 같은 책으로 등록된다.
- `GET /kosync/syncs/progress/<document>` 는 원본이 EPUB인 책에 한해 **요청한 문서의 기록과, 같은 책에 묶인 다른 문서(원본, 다른 프로필 변환본)의 기록 중 timestamp가 가장 최근인 것**을 돌려준다. 이때 응답의 `document` 는 요청한 값이고, `device`·`device_id` 는 그 기록을 올린 기기의 값이다.
- 원본이 TXT인 책은 섞지 않는다. 원본 TXT와 변환 EPUB은 구조가 달라 위치를 그대로 쓸 수 없기 때문이다.
- `PUT` 은 요청한 문서에만 저장된다. 저장 형식은 바뀌지 않았다.
- 웹 뷰어(브라우저)의 EPUB/TXT 진행률과는 연동하지 않는다.

## 7. 로컬 EPUB 업로드·변환

기기에 있는 EPUB을 서버에서 변환받는 API다. 업로드한 책은 도서관에 등록되지 않는다(별도 기능). 모든 응답은 JSON이다.

변환 프로필은 **POST 시점**의 그 계정 피드 기기(§2)다. 해시 조회·상태 조회·다운로드도 요청한 계정의 지금 피드 기기 프로필로 찾는다. POST와 상태 조회 사이에 피드 기기를 바꾸면 `404`(모름)가 나온다. 그때는 다시 올리면 된다.

### 7.1 흐름

1. **해시 조회** `GET /opds-epaper/v1/uploads/<sha256>`: 원본 전체의 SHA-256(소문자 16진수 64자)으로 이미 변환한 책인지 묻는다. `200` 이면 업로드를 건너뛰고 받으면 된다.
2. **업로드** `POST /opds-epaper/v1/uploads`: 본문은 EPUB 파일 바이트 그대로다(multipart 아님). 헤더:
   - `Content-Type: application/epub+zip`
   - `X-Content-SHA256: <sha256>` (선택, 있으면 서버가 계산한 값과 비교한다)
   - `X-Title: <제목>` (선택, 로그용)
3. **상태 조회** `GET /opds-epaper/v1/uploads/<sha256>`: `202` 인 동안 기다렸다 다시 묻는다.
4. **다운로드** `GET /opds-epaper/v1/uploads/<sha256>.epub`

### 7.2 응답

| 상태 | 본문 예 |
| --- | --- |
| `200` 변환 완료 | `{"state":"done","sha256":"…","profile":"<프로필 id, 예: v1>","digest":"<partial MD5>","size":123456,"download":"https://…/uploads/<sha256>.epub"}` |
| `202` 변환 중 | `{"state":"converting","sha256":"…","status_url":"https://…/uploads/<sha256>"}` |
| `404` 모름 | `{"state":"unknown","sha256":"…"}` |
| `422` 변환 실패 | `{"state":"failed","sha256":"…","reason":"…"}` |
| `400` 잘못된 요청 | `{"error":"bad_sha256" \| "empty" \| "not_epub" \| "sha256_mismatch"}` |
| `403` 권한 없음 | `{"error":"upload_not_allowed","message":"…"}` |
| `413` 너무 큼 | `{"error":"too_large","limit":52428800}` |

### 7.3 제한

- 업로드는 **50MB** 까지다.
- 서버는 업로드를 믿을 수 없는 입력으로 다룬다. 업로드마다 따로 만든 임시 디렉터리에서 변환하고, 변환이 끝나면 그 디렉터리를 지운다.
- ZIP 검사: 엔트리 10,000개 이하, 압축 해제 총량 512MB 이하, 1MB가 넘는 엔트리는 압축비 200배 이하. `../`, 절대 경로, 드라이브 문자가 든 엔트리 이름은 거절한다. 그 밖에 §5.5의 DRM 규칙이 적용된다.
- 업로드 변환본에는 book_id가 없으므로 §6.3의 문서 묶음에 들어가지 않는다. 진행 기록은 그 digest에만 남는다.

## 8. 캐시

| 설정 키 | 기본값 | 뜻 |
| --- | --- | --- |
| `EPAPER_CACHE_DIR` | `<설치 경로>/cache/epaper` | 캐시 위치 |
| `EPAPER_CACHE_DAYS` | 30 | 마지막 다운로드 뒤 이 일수가 지나면 지운다 |
| `EPAPER_CACHE_MAX_MB` | 2048 | 넘으면 마지막 다운로드가 오래된 것부터 지운다 |
| `EPAPER_CONVERT_TIMEOUT_SEC` | 45 | 다운로드 요청이 변환을 기다리는 최대 시간 |
| `EPAPER_UPLOAD_USERS` | (비어 있음) | 업로드 API를 쓸 수 있는 사용자 이름(쉼표 구분) |

이 키들은 관리자 설정 화면에 없다. 바꾸려면 설정 저장소(`settings` 테이블)에 직접 넣는다. 사용자별 기기 설정 `EPAPER_WEB_DEVICE`·`EPAPER_FEED_DEVICE` 는 모델 id를 저장하는 사용자 설정이다(전역값 없음, 빈 값 = 없음).

- 캐시 상한은 모든 프로필이 같이 쓴다. JPEG 프로필 변환본은 1비트 변환본보다 3~6배 크다(§5.2). 2GB는 보통 책 기준 `v1` 약 2,500권, 고해상도 약 400권이다.
- 압축을 푼 크기가 512MB를 넘는 책은 변환하지 않는다(`422`, §7.3과 같은 상한).
- 캐시 키: 도서관 책은 `<db_type>/<book_id>.<프로필>`, 업로드는 `upload/<sha256>.<프로필>`, 피드 표지는 `covers/<db_type>/<book_id>.<태그>.jpg`(`v1`) 또는 `covers/<db_type>/<book_id>.<프로필>.<태그>.jpg`(그 밖의 프로필).
- 캐시 유효성: 원본 크기·수정 시각, 전역 변환기 리비전, EPUB이면 프로필 revision(3.2.0이 만든 메타에는 값이 없고 1로 본다). TXT는 프로필 revision을 보지 않는다.
- 정리 작업은 6시간마다 돈다. 변환 중이거나 전송 중인 파일은 건너뛴다. 정리 작업이 실패하면 관리자 화면의 상태 점(시스템 상태)에 표시된다.
- 캐시는 언제 지워도 된다. 다음 다운로드 때 같은 바이트로 다시 만들어지므로 digest와 진행 기록이 그대로 유지된다(§5.6).
- MCP 도구: `epaper_cache_status`(현황, 프로필별 변환본 수·크기 `profiles`, 최근 실패 목록), `clear_epaper_cache`(비우기), `epaper_devices`(프로필·모델 목록, 사용자의 두 기기 설정), `set_epaper_device`(사용자의 기기 지정, username 필수). 쓰기 도구는 MCP 쓰기 허용이 필요하다.

## 9. 서버 로그

서버 로그에 `[EPAPER]` 로 시작하는 줄이 남는다. 비밀번호, 동기화 키, Authorization 헤더, 서명 토큰은 남기지 않는다.

| 줄 | 언제 |
| --- | --- |
| `[EPAPER] GET <경로> user=<이름> status=<코드> ms=<시간>` | 기기 피드 요청마다(인증 없는 첫 `401` 은 빼고) |
| `[EPAPER] auth failed user=<이름> path=<경로>` | 이름은 있는데 인증에 실패했을 때 |
| `[EPAPER] convert ok key=… profile=… format=… seconds=… size=… digest=… warnings=… repaired=…` | 변환 성공 |
| `[EPAPER] convert warning key=…: …` | 변환 경고(그림 유지, 폰트 범위 밖 글자 등) |
| `[EPAPER] convert over time limit key=… limit=…s` | 45초 상한을 넘겨 `503` 으로 답했을 때 |
| `[EPAPER] convert failed key=… reason=…` | 변환 실패 |
| `[EPAPER] upload accepted/refused user=… profile=… reason=…` | 업로드 접수(프로필 포함)·거절 |
| `[EPAPER] web download book=… user=… profile=…` | 웹 메뉴 "기기용 받기" |
| `[EPAPER] device setting not found user=… key=… value=…` | 저장된 기기 id가 표에 없음(없음으로 동작). 빈 값에는 남지 않는다 |
| `[EPAPER] kosync cross-document progress: user=… book=… requested=… served_from=…` | 다른 문서의 기록을 돌려줬을 때 |
| `[EPAPER] cache cleanup removed=… freed=…` | 정리 작업이 파일을 지웠을 때 |

## 10. 이 버전에 없는 것

- 기기의 `net.log` 를 받아 보관하는 엔드포인트
- 웹 뷰어 진행률과의 연동
- 업로드한 책을 도서관에 정식 등록하는 기능
- 성인 도서관, 만화, PDF의 기기 피드
- 주소나 쿼리로 프로필 고르기(프로필은 계정의 피드 기기 설정으로만 정한다)
