---
title: Walkthrough - migrator_metadata_migration
project: BookOasis
category: history
date: 2026-06-30
type: walkthrough
---
# Walkthrough: 마이그레이션 도구 CLI 대화형 설계 및 고도화 완료

Kavita에서 북오아시스(BookOasis)로 이관하려는 사용자들을 위해 `tools/migrator.py`를 대화형 프롬프트(CLI) 기반으로 고도화하고, 홈 서버 이관용 데이터 정합성 보존 리네이밍(BookOasis to BookOasis) 모듈을 성공적으로 구축했습니다.

## 작업 상세

### 1. 인터랙티브 다단계 CLI 프롬프트 적용 ([migrator.py](file:///c:/project/media_server/tools/migrator.py))
- **Step 1: 마이그레이션 모드 선택**
  - `1. Kavita ➡️ BookOasis` / `2. BookOasis ➡️ BookOasis` 분기 선택 프롬프트 구축.
- **Step 2 (Kavita 이관)**:
  - Kavita DB 및 covers 폴더 경로를 사용자 환경에 맞게 입력받으며, 기본값(Default Fallback) 자동 유출 제안.
  - 이관 시 파일 경로 해시 기반의 북오아시스 고유 표지 규격(`book_{hash}.webp`)에 맞추어 Pillow 기반 WebP 자동 인코딩 및 이미지 이관 로직 장착.
- **Step 3 (BookOasis 간 이관)**:
  - 경로 프리픽스(Old/New)를 입력받아 DB의 책 절대 경로를 일괄 리플레이스 업데이트.
  - 갱신된 절대 경로에 기반해 기존 `covers/` 하위의 해시 이미지 파일명을 동적으로 재계산해 물리 파일 리네이밍(`os.rename`) 및 DB 이미지 링킹 값 동시 치환.

### 2. 실제 Kavita DB 데이터 E2E 검증
- 사용자가 공급한 실제 Kavita 백업 DB(`test/kavita.db`)를 바탕으로 `Step 1~4` 연쇄 시뮬레이션을 수행했습니다.
- 총 **111,429권**의 대용량 만화책 도서 목록, 시리즈 매핑, 라이브러리 루트 자동 유추, 사용자별 독서 진척도(`PagesRead`, `is_completed`)가 단 8초 만에 무오류로 이관 처리 완료됨을 검증 완료하였습니다.
