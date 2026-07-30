---
title: "스케줄 조회 API 내 Rclone RC 주소 컬럼 누락 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, scheduler, rclone]
---

# 🧠 [Bugfix] 스케줄 조회 API 내 Rclone RC 주소 컬럼 누락 오류 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 환경설정 ➡️ 자동 스캔 및 스케줄 설정
- **장애 현상**: 스케줄 설정 테이블에서 원격 카테고리의 `Rclone RC 주소`를 기입하고 `저장`을 눌렀을 때 토스트 알림창은 성공적으로 뜨나, 화면 새로고침 시 인풋 필드의 입력 데이터가 유지되지 않고 빈 값(Placeholder)으로 복귀하는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 사용자가 저장 후 스케줄러가 돌아갈 때 캐시 갱신이 올바른 포트로 수행되는지와 무관하게, 브라우저 단에서 이 주소 설정을 눈으로 올바르게 모니터링하거나 재수정할 수 없어 UX에 차질을 빚음.

---

## 3. 원인 파악 (Root Cause)
- 스케줄 저장(`/api/media/libraries/<id>/schedule` [POST]) 시에는 DB 테이블의 `rclone_rc_url` 컬럼에 정상 저장되고 있었음.
- 그러나 화면 초기 진입 또는 갱신 시 타는 조회 API인 **`/api/media/libraries/schedules` [GET]** 핸들러인 `get_libraries_schedules()` 함수 내부 SQL 구문에 `rclone_rc_url` 컬럼이 누락되어 프론트엔드로 빈 문자열만 전달된 것이 원인.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [admin.py](file:///c:/project/media_server/api/admin.py#L159-L174)
- `SELECT` 쿼리에 `rclone_rc_url`을 포함시키고, 응답 딕셔너리에 추가 매핑을 진행함.

```python
# 수정 전
cursor.execute("SELECT id, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan FROM libraries ORDER BY name ASC")
...
libraries.append({
    ...
    'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0
})

# 수정 후
cursor.execute("SELECT id, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url FROM libraries ORDER BY name ASC")
...
libraries.append({
    ...
    'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
    'rclone_rc_url': r['rclone_rc_url'] or ''
})
```

---

## 5. 최종 검증 (Verification)
- 원격 홈 서버에 배포 후 스케줄 설정 테이블에서 개별 Rclone RC 포트 주소를 수정한 뒤 `저장` ➡️ 브라우저 새로고침 시에도 입력한 주소(예: `http://localhost:5573`)가 정상 고정 노출되는 것을 최종 E2E 확인하였습니다.
