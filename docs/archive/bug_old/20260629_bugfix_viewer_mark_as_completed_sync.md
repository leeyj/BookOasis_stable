---
title: "[읽음 완료] 처리 시 브라우저 블로킹 및 API 전송 누수 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, viewer, progress, synchronicity]
---

# 🧠 [Bugfix] [읽음 완료] 처리 시 브라우저 블로킹 및 API 전송 누수 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 뷰어 내 오버레이 메뉴에서 [읽음 완료] 버튼을 누를 때
- **장애 현상**: 완료 알림창("완독 처리되었습니다.")을 거쳐 뷰어를 바로 나갈 경우, 백엔드 데이터베이스에 완독 여부 및 마지막 페이지 진척도가 반영되지 않는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 사용자가 명시적으로 '읽음 완료' 수동 기입 기능을 이용하였음에도 DB 기록이 유실되어, 메인화면과 보관함 이력에서 책이 숨겨지거나 완독 배지가 달리지 않아 큰 UX 불편을 낳았습니다.

---

## 3. 원인 파악 (Root Cause)
- [viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js) 내 `markAsCompleted()` 함수에서 `comicCurrentPage`를 조정한 뒤, 서버로 명시적인 `saveProgress` 예약을 수행하지 않고 단순 DOM 갱신(`loadComicPage()`)에만 의존했습니다.
- 동시에 `alert()` 창이 호출되면서 브라우저 자바스크립트 싱글 스레드가 완전히 일시정지(블로킹)되는 도중 사용자가 즉시 뷰어를 종료해버려, 이미지 로드 기반의 기록 트리거 및 백그라운드 디바운싱 저장이 실행될 틈새가 없이 유실된 것이 원인이었습니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js#L223-L230)
- `markAsCompleted` 메소드 내에서 페이지 전환 직후 `saveProgress` 호출로 메모리 예약을 지정하였습니다.
- 곧바로 `viewer_progress.js` 내의 `flushProgress()` 동기 강제 전송 메소드를 임포트해 직렬 구동시켜, `alert` 완료창이 브라우저 스레드를 정지시키거나 사용자가 뷰어를 즉시 탈출하더라도 백그라운드에서 백엔드 API로 완독 데이터 전송을 즉시 보장하도록 조치했습니다.

---

## 5. 최종 검증 (Verification)
- 만화책 읽기 도중 하단 제어판의 [읽음 완료] ➡️ 얼럿 창 [확인] ➡️ 즉시 모달 우측 상단 닫기 클릭으로 이어지는 최속 탈출 시나리오를 구성해 수동 테스트를 수행하였습니다.
- 이탈 직후에도 백엔드 API `/api/media/progress` 호출이 완벽히 전송되어 DB 테이블 상 `is_completed = 1` 상태로 실시간 업데이트됨을 최종 확보했습니다.
