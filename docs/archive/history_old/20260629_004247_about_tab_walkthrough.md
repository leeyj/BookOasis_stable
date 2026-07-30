---
title: Walkthrough - about_tab
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

환경설정 내에 Google 스타일의 심플하고 수려한 "이 S/W는..." (About) 정보 탭을 성공적으로 추가하였습니다. 현재 로컬 구동 중인 대시보드 버전 정보와 더불어 AGPL v3 라이선스 관련 고지사항, 버전 현황 대조를 위한 깃허브 stable 저장소 바로가기 링크를 깔끔하게 통합하였습니다.

## 🛠️ 수정 사항

### 1. 백엔드 버전 조회 API 구현 ([admin.py](file:///c:/project/media_server/api/admin.py#L465-L498))
- `[GET] /api/media/about` API 라우터를 추가하여, 서버의 `/VERSION` 파일을 직접 안전하게 파싱합니다.
- 파싱된 `"dashboard"` 및 `"state"` 버전 키-값 쌍 및 공식 stable 레포지토리 URL을 JSON 포맷으로 리턴합니다.

### 2. 프론트엔드 UI/UX 마크업 및 구글 스타일 디자인 ([library_settings.html](file:///c:/project/media_server/templates/components/views/library_settings.html#L309-L342))
- 환경설정 탭 메뉴에 "이 S/W는..."을 나타내는 새로운 메뉴 버튼을 추가하였습니다.
- 중앙 정렬 레이아웃과 함께 로그인 화면과 통일성을 이루는 보석 아이콘(`<i class="fa-solid fa-gem icon-accent"></i>`)과 `BookOasis` 그라데이션 타이틀 로고를 세련되게 드로잉하였습니다.
- 깃허브 stable 버전 파일에 접근하기 편하도록 새 창 아웃링크(`https://github.com/leeyj/BookOasis_stable`)를 연계하고, 사용자 요청에 따라 **GNU AGPL v3 오픈소스 라이선스 약식 설명** 요약본을 본문에 기입하였습니다.

### 3. 비동기 탭 토글 및 데이터 렌더링 결합 ([settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js#L58-L82))
- `switchSettingsTab` 제어 흐름 내에 `about` 탭 분기를 통합하였습니다.
- 탭 활성화 시 비동기로 `/api/media/about` 백엔드 API를 조회하여, 엘리먼트(`about-ver-dashboard`, `about-ver-state`)에 현재 로드된 버전을 동적으로 주입합니다.

---

## 🧪 E2E 최종 검증 결과
- **버전 렌더링**: 환경설정 탭 중 "이 S/W는..."을 클릭하면 `VERSION` 파일의 로컬 데이터(예: `v0.2.6` / `pre-alpha`)가 오차 없이 동적으로 정상 렌더링되는 것을 확인하였습니다.
- **아웃링크 및 라이선스 확인**: stable 저장소 링크가 정상 작동하며, AGPL v3에 의거한 소스 코드 공개 고지서 문구가 예쁘게 노출되는 것을 확인하였습니다.
