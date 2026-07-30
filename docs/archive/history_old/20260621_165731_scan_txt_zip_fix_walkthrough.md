---
title: Walkthrough - scan_txt_zip_fix
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 텍스트 및 PDF 파일 스캔 시 압축 해제(BadZipFile) 오진 조치

도서 라이브러리 스캔 시 대표 표지가 없는 일반 텍스트(`.txt`) 및 PDF(`.pdf`) 파일을 대상으로 무분별하게 압축 해제(`zipfile.ZipFile`) 분석을 시도하여 `BadZipFile` 예외를 내고 에러 리포트를 오염시키던 문제를 해결했습니다.

## 변경 내용

### 백엔드 스캐너 표지 추출 로직 조건 강화
- **[MODIFY] [cover.py](file:///c:/project/media_server/tools/scanner/cover.py)**:
  - `get_series_cover_fallback` 함수 내에서 개별 도서 파일로부터 표지 이미지 자동 추출을 수행할 때, 기존의 무조건적인 `else` (zip 압축 해제 시도) 분기를 변경했습니다.
  - 파일 확장자가 명확히 `.zip` 또는 `.cbz`인 경우에만 `zipfile.ZipFile`을 통해 첫 페이지 이미지 추출을 수행하도록 `elif` 조건식을 명시했습니다.
  - 이를 통해 `.txt` 및 `.pdf` 파일의 경우 압축 해제 검사 루틴을 안전하게 건너뛰며 `None`을 반환하므로 더 이상 불필요한 스캔 예외가 유발되지 않습니다.

## E2E 및 수동 검증 결과
1. **서버 배포 및 재시작**:
   - `python deploy.py`를 실행하여 수정된 `cover.py` 코드를 원격 홈 서버(`192.168.0.20`)로 무사히 전송하고, 단독 재기동 프로세스를 정상 완료하였습니다.
2. **수동 검증 시나리오 완수**:
   - 텍스트 파일이 다수 존재하는 서재를 지정하여 라이브러리 스캔을 작동시켰습니다.
   - 스캔 완료 후 환경설정의 스캔 에러 리포트 드롭다운을 확인하여, `.txt` 파일들이 더 이상 `BadZipFile` 오류 테이블에 하나도 검출되지 않고 무결하게 패스 및 도서 DB 적재가 정상 수행된 것을 교차 확인했습니다.
