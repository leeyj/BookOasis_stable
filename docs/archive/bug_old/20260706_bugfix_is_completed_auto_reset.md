---
title: "도서 감상 완료(is_completed) 플래그 강제 리셋 버그 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "progress", "is_completed", "reset"]
---

# 도서 감상 완료(is_completed) 플래그 강제 리셋 버그 수정

## 1. 개요 및 증상
- **현상**: 사용자가 도서를 95% 이상 감상하여 정상적으로 "읽음 완료(완독)" 처리가 되었으나, 이후 해당 도서 뷰어를 다시 진입하여 첫 장을 보거나 중간 장을 감상하다가 뷰어를 닫으면, 읽음 완료 표기(`is_completed = 1`)가 미완독(`is_completed = 0`) 상태로 강제 원복(리셋)되는 버그가 확인되었습니다.
- **영향 범위**: PDF, EPUB, TXT, 만화책(ZIP/CBZ) 등 E2E 전체 뷰어에서 공통적으로 발생했던 오작동입니다.

## 2. 원인 분석
- 진척도 저장 백엔드 API 서비스(`stream_service.py` ➔ `record_progress`)에서 진행도를 수신할 때마다 실시간으로 `pages_read` 값을 분석하여 `is_completed` 값을 동적으로 다시 결정(재연산)하도록 구현되어 있었습니다.
  ```python
  if (pages_read / total_pages) >= 0.95 or pages_read >= total_pages:
      is_completed = 1
  ```
- 이로 인해 이전에 이미 완독한 책이더라도, 뷰어 재진입 등으로 인해 앞부분의 진척도가 전송되는 순간 `is_completed`가 다시 `0`으로 판단 및 DB에 덮어씌워지는(Overwrite) 심각한 연동 오류가 유발되었습니다.

## 3. 해결 방안
- [stream_service.py](file:///c:/project/media_server/services/stream_service.py): `record_progress` 내부에 **완독 리셋 방지 방어 코드**를 설계 및 주입했습니다.
  ```python
  # 기존 user_progress에서 완독 기록(is_completed)을 선조회
  cursor.execute("SELECT pages_read, is_completed FROM user_progress WHERE book_id = ? AND user_id = ?", (book_id, user_id))
  
  ...
  
  # 이미 완독된(is_completed = 1) 도서라면, 뒤이어 날아오는 pages_read 전송 건과 관계없이 완독 플래그(1) 강제 유지
  if row and row['is_completed'] == 1:
      is_completed = 1
  ```
- 사용자가 도서 카드를 우클릭하여 직접 "읽지 않음으로 표시" 기능을 선택해 DB progress를 명시적으로 지우지 않는 한, 단순 뷰어 재진입이나 탐색으로 인해 한 번 완료된 완독 표식이 리셋되지 않도록 방어했습니다.

## 4. E2E 검증 결과
- 완독한 도서를 재진입하여 감상 후 종료하더라도, 도서 목록 및 보관함 대시보드 상에서 완독(100% 읽음) 뱃지와 색상이 강제로 미독/읽는 중 상태로 복원되지 않고 온전하게 완독 상태가 보존됨을 최종 확인했습니다.
