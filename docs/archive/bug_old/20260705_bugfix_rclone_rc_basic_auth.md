---
title: "[버그수정] Rclone RC 통신 시 ID/패스워드 인증(Basic Auth) 미지원 결함 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-05
tags: [rclone, vfs, basic-auth, scanner, bugfix]
---

# 🐛 Rclone RC 통신 시 ID/패스워드 인증(Basic Auth) 미지원 결함 조치

Rclone VFS 원격 카테고리 스캔 시, Rclone RC(Remote Control) API 서버에 ID/패스워드 인증(HTTP Basic Authentication)이 설정되어 있을 경우 인증 처리를 누락하여 캐시 강제 갱신 요청(`vfs/refresh`)이 무시 및 실패하는 문제를 해결했습니다.

---

## 1. 버그 내역 및 현상
* **문제 상황**: Rclone RC 서버에 `--rc-user` 및 `--rc-pass`를 걸어둔 사용자가 카테고리 스케줄러나 강제 스캔을 구동할 때, `urllib.request.urlopen` 요청 시 HTTP 401 Unauthorized 에러가 발생하며 VFS 캐시 갱신에 실패함.
* **원인**: 
  - [vfs.py](file:///c:/project/media_server/tools/scanner/vfs.py) 내 `trigger_vfs_refresh` 함수에서 `urllib.request.Request` 객체를 만들어 전송할 때 URL에 내장된 인증 정보(`http://user:pass@host:port`)를 파싱하지 못하고 그대로 사용하거나 헤더에 `Authorization`을 바인딩하지 않아 인증 실패가 발생함.

---

## 2. 해결 방안 및 수정 사항
1. **인증 정보 파싱 및 HTTP Basic 헤더 수동 추가**:
   - `urllib.parse.urlparse`를 이용해 `rclone_rc_url`을 파싱하고, `parsed.username`과 `parsed.password`가 존재할 때 이를 Base64 인코딩하여 `Authorization: Basic {base64_hash}` 헤더를 구성하여 추가했습니다.
2. **요청 URL 정화(Sanitization)**:
   - 파이썬 `urllib.request`가 사용자 정보가 담긴 URL을 보낼 때 발생할 수 있는 잠재적 규격 에러를 방지하기 위해, 요청 전송용 URL 주소에서는 ID/비밀번호 문자열을 제외하고 순수한 `http://host:port/vfs/refresh` 형태로 주소를 재조립하여 요청하도록 개선했습니다.
3. **로그 보안성 보강**:
   - 요청 예외 발생 시 에러 로그가 출력될 때 URL 내의 평문 패스워드가 노출되지 않도록, 골뱅이(`@`) 기호가 포함된 원격 주소의 경우 자격 증명 영역을 `****:****` 형태로 마스킹하여 보안 노출을 미연에 방지했습니다.

---

## 3. 영향도 및 결과
* 이제 Rclone RC에 보안 자격 증명을 설정한 환경에서도 스캔 시 정상적으로 VFS 캐시 강제 갱신 프로세스가 작동하며, 인증 정보가 없는 로컬/기본 값의 환경도 기존과 동일하게 완벽 호환됩니다.
