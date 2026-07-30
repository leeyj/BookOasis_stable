---
title: "스캐너 엔진 engine.py 들여쓰기 오류(IndentationError) 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-19
tags: [scanner, indentation, bugfix]
---

# 🐛 스캐너 엔진 engine.py 들여쓰기 오류 조치

## 1. 버그 내역
- Gunicorn 서버 및 스캐너 워커 기동 시 `tools/scanner/engine.py` 파일의 163라인에서 `IndentationError: unexpected indent` 에러가 발생하여 서버 프로세스가 구동 도중 비정상 종료되는 현상.

## 2. 영향도
- 전체 미디어 서버 웹 애플리케이션 및 백그라운드 스캐너 프로세스 기동 불가 (서비스 중단).

## 3. 수정 사항
- 대상 파일: [engine.py](file:///c:/project/media_server/tools/scanner/engine.py#L162-L173)
- 수정 내용:
  - `traversal_errors`가 존재할 시 폴더 순회 부분 실패에 따라 삭제/이동 동기화를 우회하는 예외 처리 방어 코드 블록의 잘못된 들여쓰기(Indent) 레벨을 4칸 들여쓰기로 정상 보정.

## 4. 해결 사항
- 들여쓰기를 올바르게 정렬하여 구문 오류(Syntax/Indentation Error)를 해결하였습니다.
- 수정 사항을 원격 운영 서버(`192.168.0.20`)에 재배포(`deploy.py`)하여 서버 기동 및 헬스 체크 정상 통과(웹 서비스와 스캐너 워커 기동 완료)를 검증하였습니다.
