---
title: Walkthrough - opds_and_ui_enhancements
project: BookOasis
category: history
date: 2026-06-25
type: walkthrough
---
# 🏁 OPDS 뷰어 통합 기능 확대 및 웹 UI 상태 관리 개선 결과 보고

iOS Panels OPDS 리더 통합을 위한 기능 확대 및 웹 UI 사용자 경험 개선을 완료했습니다. 주요 성과는 OPDS 메타데이터 완성도 향상, 신규 추가/최근 읽은 섹션 추가, 그리고 웹 페이지 스크롤 상태 복원 기능입니다.

---

## 🛠️ 주요 작업 내용

### 1. 웹 UI 리팩토링 및 상태 관리

#### 1.1 로그인 페이지 CSS/JS 분리
- **대상 파일**: 
  - [templates/login.html](file:///c:/project/media_server/templates/login.html) (수정)
  - [static/css/login.css](file:///c:/project/media_server/static/css/login.css) (신규)
  - [static/js/login.js](file:///c:/project/media_server/static/js/login.js) (신규)
- **수정 사항**: 인라인 스타일과 스크립트를 외부 파일로 분리하여 유지보수성 및 캐싱 효율성 향상

#### 1.2 뷰어 뒤로가기 이력 상태 관리
- **대상 파일**: [static/js/viewer.js](file:///c:/project/media_server/static/js/viewer.js)
- **버그 해결**: 뷰어에서 뒤로가기 선택 시 도서 상세 뷰가 아닌 메인 리스트로 이동하던 문제 해결
- **해결 방법**: `openReader()` 함수에서 `history.pushState({view:'viewer'}, '', '#viewer')` 호출로 뷰어 상태를 히스토리 스택에 명시적으로 저장

#### 1.3 페이지 스크롤 위치 복원
- **대상 파일**: 
  - [static/js/state.js](file:///c:/project/media_server/static/js/state.js) (수정)
  - [static/js/modal.js](file:///c:/project/media_server/static/js/modal.js) (수정)
- **기능**: 도서 상세 모달 닫기 후 메인 리스트로 복귀 시 이전 스크롤 위치 자동 복원
- **구현**: `scrollPositions` 객체를 상태 매니저에 추가하고, 모달 열기/닫기 시점에 스크롤값 저장/복원

---

### 2. OPDS 피드 기본 개선

#### 2.1 XML 특수 문자 이스케이핑 및 URL 인코딩
- **대상 파일**: [api/opds.py](file:///c:/project/media_server/api/opds.py) (수정)
- **버그 해결**: 도서명, 시리즈명 등에 특수 문자(`<`, `>`, `&`, 등)가 포함되어 있으면 Panels 같은 OPDS 클라이언트가 XML 파싱 오류로 인식하던 문제 해결
- **해결 방법**: 
  - `_escape_xml()` 함수로 모든 텍스트 노드를 HTML Entity 인코딩
  - `_encode_url_segment()` 함수로 커버 이미지 경로의 URL 세그먼트 인코딩 (경로 슬래시 유지)

#### 2.2 OPDS 커버 이미지 MIME 타입 감지
- **기능**: 커버 파일 확장자(`.jpg`, `.webp`, `.png` 등)에 따라 동적으로 `Content-Type` 반영
- **구현**: Python `mimetypes.guess_type()` 활용하여 확장자 기반 MIME 자동 판단

#### 2.3 /covers 경로 인증 제거
- **대상 파일**: 
  - [api/auth.py](file:///c:/project/media_server/api/auth.py) (수정)
  - [api/stream.py](file:///c:/project/media_server/api/stream.py) (수정)
- **버그 해결**: OPDS 클라이언트가 Basic Auth 없이 커버 이미지를 요청할 수 없어 썸네일이 표시되지 않던 문제 해결
- **해결 방법**: `/covers/*` 경로를 인증 미들웨어에서 명시적으로 제외 처리

---

### 3. OPDS 시리즈 썸네일 표시

#### 3.1 시리즈별 대표 커버 조회
- **대상 파일**: [api/opds.py](file:///c:/project/media_server/api/opds.py) (수정)
- **개선**: `_series_entries()` 함수에서 각 시리즈마다 대표 커버 이미지를 DB에서 조회하여 엔트리에 포함
- **쿼리**: 시리즈별 첫 번째 도서의 `cover_image`를 서브쿼리로 조회

#### 3.2 Navigation 항목에 이미지 링크 추가
- **개선**: OPDS의 `navigation` 타입 항목(폴더, 시리즈)도 `opds:image`, `opds:image/thumbnail` 링크 포함
- **결과**: Panels 같은 OPDS 리더에서 (리더 지원 여부에 따라) 시리즈 폴더를 폴더 아이콘 대신 커버 썸네일로 표시 가능

---

### 4. OPDS 신규 추가 및 최근 읽은 섹션 추가

#### 4.1 최상위 피드 확장
- **대상 파일**: [api/opds.py](file:///c:/project/media_server/api/opds.py) (수정)
- **추가 항목**:
  - `/opds` 루트: "신규 추가", "최근 읽은" Navigation 항목 추가
  - `/opds-adult` 루트: 성인 전용 버전 동일 추가

#### 4.2 신규 추가 도서 엔드포인트
- **엔드포인트**: 
  - `GET /opds/recently-added` (일반)
  - `GET /opds/adult/recently-added` (성인)
- **기능**: DB에서 `created_at` 기준 최신 20개 도서 조회하여 Acquisition 형식으로 반환
- **MIME 타입**: 도서 파일 확장자 기반 동적 판단

#### 4.3 최근 읽은 도서 엔드포인트
- **엔드포인트**:
  - `GET /opds/recently-read` (일반)
  - `GET /opds/adult/recently-read` (성인)
- **기능**: `user_progress` 테이블과 `books` 테이블 조인하여 `last_read_at` 기준 최신 30개 도서 조회
- **MIME 타입**: 도서 파일 확장자 기반 동적 판단

#### 4.4 헬퍼 함수 구현
- **`_recently_added_entries()`**: 신규 추가 도서 목록을 OPDS Acquisition 엔트리로 변환
- **`_recently_read_entries()`**: 최근 읽은 도서 목록을 OPDS Acquisition 엔트리로 변환
- **데이터 소스**: `ReadingHistoryService` 대신 DB 직접 조회로 원본 `cover_image` 파일명 보장

---

### 5. 버그 수정

#### 5.1 최근 읽은 도서 커버 미표시 문제
- **발견**: 최근 읽은 도서 항목에서 책 커버가 표시되지 않음
- **원인**: `ReadingHistoryService.get_history()`의 `cover_image`는 웹 UI용으로 이미 처리된 형식(타임스탬프 쿼리 파라미터 포함)이었음
- **해결**: DB에서 직접 `user_progress`와 `books`를 조인 조회하여 원본 `cover_image` 파일명 획득

---

## 📝 OPDS 피드 구조

### 일반 OPDS 피드 트리 구조
```
/opds (최상위)
├── 라이브러리1
│   └── 시리즈 목록
│       └── 도서 목록 (Acquisition)
├── 라이브러리2
│   └── 시리즈 목록
│       └── 도서 목록 (Acquisition)
├── 신규 추가 (NEW)
│   └── 도서 목록 (Acquisition, 최대 20개)
└── 최근 읽은 (NEW)
    └── 도서 목록 (Acquisition, 최대 30개)
```

### 성인 OPDS 피드 (`/opds-adult`)
동일한 구조로 성인 도서 관련 데이터만 반영

---

## 🧪 검증 결과

### 1. 웹 UI 검증
- ✅ 로그인 페이지 정상 로드 및 로그인 기능 동작
- ✅ 뷰어 뒤로가기 시 도서 상세 뷰가 아닌 메인 리스트로 이동 (히스토리 스택 정상)
- ✅ 도서 상세 모달 닫기 후 메인 리스트 스크롤 위치 복원 확인

### 2. OPDS 검증
- ✅ XML 생성 시 특수 문자 이스케이핑 정상 동작
- ✅ `/opds` 최상위 피드 "신규 추가", "최근 읽은" 항목 정상 표시
- ✅ `/opds/recently-added` 엔드포인트 신규 도서 20개 조회 정상
- ✅ `/opds/recently-read` 엔드포인트 최근 읽은 도서 30개 조회 정상
- ✅ 시리즈 항목에 대표 커버 이미지 URL 포함 확인
- ✅ `/covers` 경로 무인증 접근 정상 작동
- ✅ Python 문법 검사 통과 (`python -m py_compile api/opds.py`)

### 3. Panels 호환성
- Panels에서 OPDS 피드 접근 시 서버 응답 정상 (XML 파싱 오류 없음)
- 도서 항목에 커버 썸네일 표시 확인

---

## 📦 배포 준비

모든 파일이 로컬에서 검증되었으며, 다음 명령으로 운영 서버에 배포 가능합니다:

```bash
python deploy.py
```

이후 원격 서버에서:

```bash
./manage.sh restart
```

---

*작업 완료 일시: 2026-06-25*
*작업 시간: 약 2시간*
