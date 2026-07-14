---
title: "1 컨테이너 2 프로세스 (웹/워커 분리) 아키텍처 구현 계획서"
description: "Redis 없이 기존 인메모리 큐를 활용하며, 단일 도커 컨테이너 내에서 프로세스를 분리해 GIL 병목을 우회하는 설계안"
date: 2026-07-14
---

# 🚀 1 컨테이너 2 프로세스 아키텍처 구현 계획 (Handover)

## 1. 개요 및 목표
현재 미디어 서버는 단일 파이썬 프로세스 내에서 웹 서버와 무거운 백그라운드 스캐너를 함께 구동하여 **파이썬 GIL(Global Interpreter Lock)** 병목으로 인한 대시보드 지연(524 에러) 현상이 발생하고 있습니다.
도커 사용자의 배포 환경(1 컨테이너)을 그대로 유지하면서, Redis와 같은 무거운 외부 의존성 없이 이 문제를 완벽히 해결하는 아키텍처 전환 계획입니다.

## 2. 설계 핵심 (Architecture Design)
파이썬의 `multiprocessing` 모듈을 활용하여 1개의 컨테이너 안에서 **2개의 독립된 OS 프로세스**를 띄웁니다.

- **Process A (Web Server - 5930 포트)**
  - 오직 사용자 HTTP 요청(대시보드 렌더링, 뷰어 서빙 등)만 처리합니다.
  - 무거운 I/O나 연산을 하지 않으므로 반응성이 극대화됩니다.
- **Process B (Worker Server - 5931 포트, 내부용)**
  - 기존에 완성되어 있는 `scanner_queue.py` (인메모리 큐)를 여기서 구동합니다.
  - 스캔 등 CPU/디스크를 많이 쓰는 작업을 독점합니다.
  - Web Server의 요청을 받기 위해 외부에 노출되지 않는 가벼운 내부용 HTTP API(FastAPI/Flask)를 띄웁니다.

## 3. 통신 흐름 (프로세스 간 통신, IPC)
두 프로세스는 컨테이너 내부의 `localhost(127.0.0.1)` 루프백 주소를 통해 통신합니다. DB 락을 유발하지 않으며 매우 빠릅니다.

1. **스캔 요청:** 사용자가 UI에서 스캔을 누르면 Web Server가 `POST http://127.0.0.1:5931/internal/scan` 호출. Worker가 자기 메모리 큐에 적재.
2. **진행 상황 조회:** Web Server가 대시보드를 그릴 때 `GET http://127.0.0.1:5931/internal/status` 호출. Worker가 현재 스캔 진척률 반환.

## 4. 단계별 구현 계획 (Task Breakdown)

### Phase 1: 워커 전용 미니 서버 구축 (`services/worker_app.py` 신설)
- 기존 `scanner_queue.py`를 임포트하여 제어하는 아주 가벼운 Flask(또는 FastAPI) 앱 작성.
- 엔드포인트 구현: `/internal/scan`, `/internal/status`, `/internal/cancel` 등.

### Phase 2: Web Server 통신 로직 변경 (`services/scanner_service.py` 수정)
- Web Server에서 기존에 `scanner_queue.enqueue()`를 직접 호출하던 코드를 모두 들어냅니다.
- 대신 `requests.post('http://127.0.0.1:5931/internal/scan')` 형태로 워커에 API 요청을 보내도록 프록시(Proxy) 로직을 구현합니다.

### Phase 3: 메인 진입점 프로세스 분기 (`core.py` 수정)
- 애플리케이션 시작 시(구동 스크립트), `multiprocessing.Process`를 사용하여 Web Server 모듈과 Worker Server 모듈을 동시에 백그라운드로 띄웁니다.
- **안전성(Graceful Shutdown) 확보:** 메인 부모 프로세스가 종료(SIGTERM/SIGINT)될 때, 분기된 Web과 Worker 자식 프로세스도 고아(Orphan) 상태로 남지 않고 깔끔하게 종료되도록 `signal` 핸들링 로직을 추가합니다.

## 5. 예상되는 리스크 및 대처 방안
1. **자원 경합:** 두 프로세스가 동시에 SQLite DB에 쓰기를 시도할 수 있습니다.
   * **대처:** 이미 적용되어 있는 WAL(Write-Ahead Logging) 모드가 이 문제를 훌륭하게 방어합니다. 워커 프로세스가 대량 쓰기를 할 때 트랜잭션을 쪼개서 커밋(청크 단위 처리)하도록 안전장치를 강화합니다.
2. **메모리 증가:** 프로세스를 분리하므로 애플리케이션의 기본 램(RAM) 사용량이 약 30~50MB 정도 증가할 수 있습니다.
   * **대처:** 미디어 서버 특성상 허용 가능한 수준의 미미한 증가치이므로 모니터링만 유지합니다.
