---
title: Walkthrough - metadata_close_modal_name_loss
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

모달창이 닫히는 과정에서 전역 변수 초기화로 인해 리렌더링 시리즈명이 `null`로 손상되던 문제를 최종적으로 완벽히 조치하였습니다.

## 🛠️ 수정 사항

### 1. 모달 닫기 전 시리즈명 로컬 백업 적용 ([metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js))
- `closeMetadataSearchModal()` 호출 시 `currentSeriesName` 전역변수가 `null`로 초기화되는 구조를 파악했습니다.
- 모달을 닫기 전 `seriesNameToRefresh` 로컬 상수에 현재 시리즈명을 먼저 백업해두고, 모달이 닫힌 뒤 `openBookDetail` 호출 시 이 백업 데이터를 사용하도록 수정했습니다.

---

## 🧪 E2E 최종 검증 결과
- **디버그 콘솔 출력 검증**: 3단계 상세 새로고침 로그에서 `currentSeriesName: "나 혼자 탑에서 농사"`, `activeLibId: "4"` 파라미터가 정확하게 복구되어 API를 정상 호출하는 것을 확인했습니다.
- **실시간 UI 복구**: 모달이 닫힌 뒤 화면 설명, 표지(WebP), 단행본 목록(1권)이 정상적으로 노출되며 메타데이터 적용이 완료되는 것을 최종 검증하였습니다.
