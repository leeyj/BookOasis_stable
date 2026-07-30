---
name: logs_archiving
description: scanner.log 및 lazy_scanner.log의 자동 10MB 기준 zip 아카이빙 로직 연동
---

# 📝 [기능개선] scanner.log 및 lazy_scanner.log 파일 자동 zip 아카이빙(Rotation) 연동

용량이 커지던 `scanner.log`와 `lazy_scanner.log` 파일에 대해 기존 `media_server.log`처럼 **10MB 용량 초과 시 자동 zip 압축 회전(Rotating)이 수행되도록 통합 범용 로거 시스템을 이행**했습니다.

## 1. 분석 및 설계
* **현상**: `media_server.log`는 `ZipRotatingLogger`를 통해 10MB 단위로 아카이빙 압축되어 관리 중이었으나, `scanner.log` 및 `lazy_scanner.log`는 무제한 append 방식(`with open('...', 'a')`)으로 작성되어 각각 164MB, 80MB에 달하는 디스크 용량 누적 현상을 일으켰습니다.
* **해결 방안**:
  * `ZipRotatingLogger` 클래스가 특정 로그명에 국한되지 않고, 투입된 원본 파일명에 연동되어 `[파일명]_[타임스탬프].zip` 형태로 동적 아카이빙을 수행하도록 일반화시켰습니다.
  * 스캐너 제어 인쇄 로거(`tools/scanner/logger.py`) 및 독립 백그라운드 스캐너(`tools/lazy_scanner.py`) 내부의 `custom_print` 출력 스트림을 일반 파일 스트림 대신 `ZipRotatingLogger` 인스턴스로 교체 연동하여, 10MB 도달 시 실시간 자동 회전 압축이 적용되도록 처리했습니다.

## 2. 해결 방법
* **[utils/logger.py](file:///c:/project/media_server/utils/logger.py)**:
  * `ZipRotatingLogger` 내부에서 `self.filename = os.path.basename(filepath)` 속성을 추출하여 zip 아카이브명을 동적으로 결정하도록 로직을 리팩토링했습니다.
* **[tools/scanner/logger.py](file:///c:/project/media_server/tools/scanner/logger.py)**:
  * `scanner.log` 전용 `ZipRotatingLogger(log_file_path, 10 * 1024 * 1024)` 인스턴스를 유지하여, 스캔 중 콘솔 출력 및 로깅이 발생할 때 10MB 기준 회전 압축이 돌도록 바인딩했습니다.
* **[tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py)**:
  * `lazy_scanner.log` 전용 `ZipRotatingLogger` 인스턴스를 결합하여, 백그라운드 표지 추출 로깅 시 자동 아카이빙을 구현했습니다.

## 3. 임시 실행 및 용량 소거 완료
* 패치 배포 완료 후, 원격지 서버에 1회성 트리거를 전달하여 이미 쌓여있던 164MB 분량의 `scanner.log` 및 80MB 분량의 `lazy_scanner.log` 파일을 즉시 `scanner.log_[타임스탬프].zip` 등으로 즉각 강제 아카이빙 압축하고 원본 파일 크기를 0으로 리셋 완료하여 디스크 점유 용량을 성공적으로 전량 확보했습니다.

## 4. 수정 파일 목록
* [utils/logger.py](file:///c:/project/media_server/utils/logger.py) (범용 Zip 회전 로거 고도화)
* [tools/scanner/logger.py](file:///c:/project/media_server/tools/scanner/logger.py) (스캐너 로깅 래핑 교체)
* [tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py) (백그라운드 스캐너 로깅 래핑 교체)
