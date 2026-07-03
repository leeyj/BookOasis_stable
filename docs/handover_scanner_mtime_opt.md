---
title: "인수인계서: 스캐너 Mtime 기반 광속 캐싱 최적화"
date: 2026-07-03
---

# 📝 인수인계서: 스캐너 Mtime 기반 광속 캐싱 최적화 (Handover)

## 1. 현재 상황 및 문제점 (Background & Problem)
- **성공적인 1차 최적화:** VFS 사전 갱신 보장 및 하이브리드 Bulk Insert(트랜잭션) 도입으로, 변경 사항이 없는 폴더 7만 개를 단 102초 만에 스킵(Ultra-fast skip)하는 데 성공했습니다.
- **새로운 병목 발견:** 폴더 내에 `kavita.yaml` 또는 `info.xml` 같은 메타데이터 파일이 존재하는 카테고리의 경우, 스캐너가 해당 파일이 **언제 수정되었는지 알 수 없어 매번 무조건 파일을 열어보고 DB를 업데이트**하고 있습니다.
- **결과적 한계:** 거의 모든 폴더에 `kavita.yaml`이 존재하는 카테고리에서는 rclone 네트워크 드라이브를 통해 수만 개의 파일을 일일이 열어보는 막대한 I/O가 발생하여, 결국 과거의 느린 속도로 회귀하는 현상이 확인되었습니다.

## 2. 내일 진행할 목표 (Goal)
- **변경 사항이 없는 메타데이터 파일 캐싱:** 폴더와 메타데이터 파일의 **최종 수정 시간(`mtime`)**을 DB에 기록해두고, 시간이 변하지 않은 폴더는 파싱을 100% 생략하고 즉시 스킵(Ultra-fast skip)하도록 스캐너를 고도화합니다.

## 3. 상세 구현 설계안 (Implementation Plan)

### Step 1: 데이터베이스 스키마 추가 (`database.py`)
디렉토리와 메타데이터 파일의 시간을 기억할 테이블을 신설합니다.
```sql
CREATE TABLE IF NOT EXISTS folder_mtimes (
    folder_path TEXT PRIMARY KEY,
    dir_mtime REAL,
    meta_mtime REAL
);
```

### Step 2: 스캐너 로직 변경 (`tools/scanner/core.py`)
`_scan_library_internal` 및 `process_folder_task` 내부의 스킵 판정 로직을 업그레이드합니다.
1. `os.path.getmtime(root)`을 통해 현재 폴더의 갱신 시간 획득.
2. `kavita.yaml`이 존재할 경우 `os.path.getmtime(yaml_path)` 획득.
3. DB에 저장된 `folder_mtimes` 데이터와 비교:
   - **일치함:** 파일 추가/삭제도 없었고(폴더 mtime 동일), 메타데이터 수정도 없었음(yaml mtime 동일). 👉 **즉시 Early Return (광속 스킵)!**
   - **불일치함:** 기존처럼 정상적으로 메타데이터를 파싱하고 DB에 도서 정보를 업데이트한 뒤, `folder_mtimes` 테이블의 시간 정보도 최신으로 갱신 (UPSERT).

### Step 3: 엣지 케이스 및 예외 처리
- **강제 스캔 (Force Scan):** 사용자가 대시보드에서 '전체 강제 스캔'을 지시한 경우에는 `mtime` 일치 여부를 무시하고 무조건 전부 덮어쓰도록 처리해야 합니다.
- **로컬 vs 클라우드:** `is_remote` 환경에서도 `os.path.getmtime`은 VFS 캐시를 통해 즉시 응답하므로 병목 없이 작동할 것입니다.

## 4. 인수인계 노트 (Note for Next Agent)
이 문서를 읽은 다음 에이전트는, **"스캐너에 mtime 캐싱 로직을 구현하자"**는 목표를 인지하고 위 설계안을 바탕으로 `database.py`와 `core.py`를 리팩토링하는 작업을 진행해 주십시오. 
사용자에게 사전 `implementation_plan.md` 승인을 받은 후 진행하면 됩니다.
