---
id: bugfix-20260702-comic-viewer-400
date: 2026-07-02
type: bugfix
severity: high
status: fixed
affected_files:
  - static/js/viewer/workers/image_worker.js
  - api/stream.py
  - static/js/viewer/renderer.js
---

# 버그 수정 보고서: 만화 뷰어 이미지 로드 400 에러

## 버그 내역

브라우저 콘솔에서 다음 에러가 발생:
- `Failed to load resource: the server responded with a status of 400 ()` (stream:1)
- `[Viewer-Comic] Image load failed: page_idx=0` (renderer.js:345)
- `[Viewer-Progress] Flushing progress: book_id=749064, page_idx=0/156` (viewer_progress.js:96)

만화 뷰어에서 첫 페이지(page_idx=0)부터 이미지 로드에 실패하며, 이후 모든 페이지 탐색이 불가능한 상태가 됩니다.

## 영향도

- **영향 범위**: 만화(ZIP/CBZ) 뷰어 전체
- **심각도**: 높음 (콘텐츠 열람 불가)
- **발생 조건**: Worker가 활성화된 브라우저 환경 (모든 최신 브라우저)

## 원인 분석

### 원인 1: `image_worker.js` — credentials 누락 (핵심)

Web Worker 컨텍스트에서 `fetch(url)` 시 credentials 옵션 미지정으로 세션 쿠키가 누락.
`@login_required` 인증 실패 또는 Worker 오류 → fallback 재시도 반복.

### 원인 2: `stream.py` — book_id 타입 불일치

`request.args.get('book_id')`는 문자열(str)을 반환하나, DB의 book_id는 정수(INTEGER).
타입 불일치로 book_offsets 쿼리 실패 → extract_page가 None 반환 → 서버 400 응답.

### 원인 3: `renderer.js` — onerror 중복 트리거

Worker fetch 실패 → fallback `img.src = url` 재시도 → 서버 에러 → onerror 재발.
사전에 `imageElements[index] = imgEl`을 동기적으로 설정하는 경쟁 조건도 존재.

## 수정 사항

| 파일 | 수정 내용 |
|------|-----------|
| `static/js/viewer/workers/image_worker.js` | `fetch(url, { credentials: 'include' })` 추가 |
| `api/stream.py` | `book_id = int(book_id)` 타입 캐스팅 및 유효성 검사 추가 |
| `static/js/viewer/renderer.js` | `_errorFired` 플래그 추가로 onerror 중복 방지, Worker fallback 경고 로그 추가, 사전 imageElements 설정 제거 |

## 해결 사항

- Worker fetch 시 세션 쿠키 정상 전달로 인증 통과
- book_id 정수 변환으로 DB 쿼리 타입 불일치 해소
- onerror 중복 트리거 방지로 에러 메시지 노이즈 감소
