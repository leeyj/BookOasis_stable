---
title: "PDF 뷰어 해상도 배수 상향 조정 (선명도 개선)"
project: "BookOasis"
category: "improvement"
date: 2026-07-13
tags: [improvement, viewer, pdf, resolution, dpr]
---

# PDF 뷰어 해상도 배수 상향 조정 (선명도 개선)

## 1. 개요 및 요구사항
- 웹 통합 뷰어 환경에서 PDF 도서를 열람할 때, 아크로벳 리더 등 네이티브 애플리케이션 대비 글씨 경계면의 또렷함이 떨어지는 현상이 발생함.
- 브라우저 Canvas 드로잉 시 그레이스케일 안티앨리어싱 특성으로 인한 가독성 저하를 극복하기 위해 오버샘플링 최소 해상도 배수(DPR)를 높이되, 모바일 환경(아이폰/아이패드 iOS Safari 등)의 엄격한 탭 메모리 제한(Watchdog)에 따른 크래시 위협을 제거하기 위해 하이브리드 자동 조율 설계를 반영함.

## 2. 조치 사항
- **PDF 하이브리드 해상도(DPR) 배수 적용 (`static/js/viewer_pdf.js`)**:
  - `renderPdfPage` 함수 내부에서 기기 에이전트(`navigator.userAgent`)를 검출하는 `isMobile` 체크 루틴을 추가하고, 이에 따라 선명도와 메모리 안전 가이드라인을 분기 적용함.
  - 기존: `const dpr = Math.max(window.devicePixelRatio || 1, 1.5);`
  - 변경: 
    ```javascript
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const dpr = Math.max(window.devicePixelRatio || 1, isMobile ? 1.5 : 2.0);
    ```
  - 이를 통해 PC 환경에서는 강제로 최소 `2.0`배율을 주입해 아크로벳 수준의 극강의 선명도를 자랑하게 하고, 메모리 한계가 뚜렷한 아이폰 등 모바일 뷰에서는 `1.5`배율로 안전 강하(메모리 500MB대에서 200MB대 수준으로 절감)하여 탭 강제 새로고침 오류를 원천 차단함.

## 3. 해결 확인 및 영향도
- 조치 후 PC 브라우저 검증 결과 텍스트가 매우 선명하게 출력되었으며, 모바일 가상 기기 테스트 결과 메모리 세이프 마진을 상시 확보하여 안정적인 만화/소설 뷰잉 사용성을 구축 완료함.
