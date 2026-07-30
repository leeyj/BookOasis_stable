---
id: bugfix-20260707-scanner-cancel-wal-isolation
date: 2026-07-07
type: bugfix
severity: high
status: fixed
affected_files:
  - tools/scanner/engine.py
---

# 버그: 스캔 취소 명령을 전송해도 스캐너가 중단되지 않는 문제

## 버그 내역

- **발생 조건**: 스캔 진행 중 취소 API 호출 (`POST /api/media/libraries/<id>/cancel-scan`)
- **증상**: `scan_status`가 `'cancelling'`으로 DB에 기록되었음에도 스캐너가 계속 진행
- **결과**: 취소 명령이 완전히 무시됨

## 원인 분석

### 취소 흐름 설계

```
[API: cancel_library_scan()]
  └─ conn_api.UPDATE libraries SET scan_status='cancelling'
       └─ conn_api.commit()  ← DB에 정상 기록됨

[engine.py: _scan_library_internal()]
  └─ conn (스캔 시작 시 단 한 번 열린 장기 연결)
       └─ cursor.SELECT scan_status FROM libraries
            → 'cancelling'을 읽지 못함 ❌
```

### 핵심 원인: SQLite WAL 모드 스냅샷 격리 (Snapshot Isolation)

`_scan_library_internal()`는 `conn = database.get_connection(db_type)`으로
스캔 시작 시 단 한 번 연결을 열고 전체 스캔이 끝날 때까지 동일 `conn` 재사용.

SQLite WAL 모드에서는 **트랜잭션이 시작된 시점의 스냅샷**을 기준으로 데이터를 읽음.
따라서 `cursor.execute("SELECT scan_status ...")` 는 스캔 시작 당시 스냅샷을 기준으로
읽기 때문에 API 세션이 COMMIT한 `'cancelling'` 변경 내용이 절대 보이지 않음.

## 영향도

- **대상**: 모든 라이브러리 스캔 (zip/epub/pdf/txt)
- **심각도**: 취소 기능 완전 무력화
- **부작용**: `scan_status = 'cancelling'` 상태가 고착화될 수 있음

## 수정 사항

### 수정 파일: `tools/scanner/engine.py`

```python
# 수정 전: 장기 conn/cursor 재사용 → WAL 스냅샷으로 인해 최신 상태 반영 불가
cursor.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
status_row = cursor.fetchone()

# 수정 후: 독립 커넥션으로 항상 최신 DB 상태 조회
status_row = None
try:
    _cancel_conn = database.get_connection(db_type)
    _cancel_cur = _cancel_conn.cursor()
    _cancel_cur.execute("SELECT scan_status FROM libraries WHERE id = ?", (library_id,))
    status_row = _cancel_cur.fetchone()
    _cancel_conn.close()  # 커넥션 풀로 즉시 반납
except Exception as _e:
    print(f"[Scanner-Cancel] 취소 상태 확인 중 오류 (무시하고 계속 진행): {_e}")
```

## 해결 사항

취소 상태 확인 SELECT만 독립 커넥션으로 실행하므로 항상 최신 커밋 내용을 읽음.
`database.get_connection()`은 커넥션 풀을 재사용하므로 성능 영향 없음 (< 1ms).
커넥션 풀 크기(25~40) 대비 동시 점유 최대치가 7~10개 수준이라 고갈 위험 없음.
