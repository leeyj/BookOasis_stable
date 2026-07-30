---
title: "MuPDF PDF 파싱 에러 상세 리포팅 보강"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [mupdf, pdf, error-handling, lazy-scanner]
---

# MuPDF PDF 파싱 에러 상세 리포팅 보강

## 1. 버그 및 개선 내역
- MuPDF 라이브러리(fitz)에서 손상되었거나 형식이 깨진 PDF 문서를 로딩 및 렌더링할 때 발생하는 오류(`expected object number`, `too many kids in page tree` 등)가 단순 일반 Exception으로 처리되어 스캔 리포트에서 오류의 상세한 원인을 파악하기 어려웠던 부분을 개선했습니다.

## 2. 영향도
- **영향 범위**: Lazy 스캐너(`tools/lazy_scanner.py`)
- **개선 효과**: PDF 포맷 내부의 심각한 오류가 감지될 경우 스캔 리포트에 `MuPDFFormatError` 코드로 확실히 구별되어 기록되므로, 사용자는 파일이 손상되었는지 여부를 직관적으로 판단할 수 있게 됩니다.

## 3. 수정 사항
- **수정 소스 파일**: [lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py)
- **수정 내용**:
  - `run_lazy_cover_extraction`에서 `Exception` 포착 후 매핑하는 조건 분기 내에 `.pdf` 확장자 체크 및 `mupdf`, `syntax error`, `page tree`, `cannot open`, `fitz` 등의 예외 메시지 문자열 매칭 조건을 추가하였습니다.
  - 조건 일치 시 에러 타입이 `MuPDFFormatError`로 리포트에 기록됩니다.

## 4. 해결 사항
- 이제 비정상적인 PDF 파일 파싱 에러가 발생 시 예외 원인이 "MuPDFFormatError" 형태로 명시적으로 보고되어 진단 가능합니다.
