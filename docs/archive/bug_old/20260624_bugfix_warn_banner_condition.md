---
title: "만화 상세 리스트 경고 배너 조건 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-24
tags: [modal, warn-banner, page-count, cover, ui]
---

# 버그 내역

만화 상세 리스트(`openBookDetail`)에서 단행본 목록을 렌더링할 때, 거의 대부분의 볼륨 카드에
"⚠ 페이지 수 미검출 — 정상 열람이 어려울 수 있습니다." 경고 배너가 잘못 표시됨.

# 원인 분석

`static/js/modal.js`의 경고 배너 표시 조건이 `||`(OR) 논리 연산자로 되어 있었음.

```js
// 버그 코드 (수정 전)
const needsWarn = noCover || noOffsets;
```

- `noCover`: 커버 이미지가 없음
- `noOffsets`: zip/cbz 포맷이면서 `total_pages === 0` 또는 `has_offsets === 0`

직전 작업(20260623_improvement_shared_cover.md)에서 시리즈 폴더의 대표 표지 공유 최적화 후,
커버는 정상적으로 등록되어 있어도 `has_offsets`나 `total_pages` 값에 따라 `noOffsets = true`가
되는 케이스가 많아지면서 OR 조건이 대부분을 매칭하게 되어 거의 모든 카드에 경고 배너가 표시됨.

# 영향도

- **영향 범위**: 만화 시리즈 상세 뷰 내 단행본 목록 전체
- **심각도**: Medium — 실제 열람에는 지장 없으나 잘못된 경고로 사용자 혼란 유발

# 수정 사항

**파일**: `static/js/modal.js` (Line 69)

```diff
- const needsWarn = noCover || noOffsets;
+ // 페이지 미검출 단독 or 커버 단독으로는 배너 미표시; 두 조건 모두 해당될 때만 표시
+ const needsWarn = noCover && noOffsets;
```

경고 배너는 **"커버 미검출 + 페이지 미검출"** 두 조건이 **동시에** 충족될 때만 표시되도록 변경.
커버만 없거나, 페이지 정보만 없는 경우는 배너 없이 정상 표시.

# 해결 사항

만화 시리즈 상세 리스트에서 커버가 정상 등록된 볼륨은 경고 배너가 표시되지 않으며,
커버와 페이지 정보가 모두 없는 실제 불량 항목에만 배너가 정확히 표시됨.
