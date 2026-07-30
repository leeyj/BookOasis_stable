# 20260707_bugfix_scheduler_vfs_rc_url_mismatch.md

---
type: bugfix
date: 2026-07-07
status: resolved
files:
  - services/scheduler_service.py
---

## 버그 내역

스케줄러 스캔 시 VFS 캐시 새로고침 API 호출에서 `Name or service not known` DNS 해석 실패 에러 발생.
`curl`로 직접 호출하면 정상 동작하지만, Python `urllib`에서만 실패하는 현상.

```
[2026-07-07 22:16:50] VFS update request failed (GDRIVE/READING/만화/연재): <urlopen error [Errno -2] Name or service not known>
[2026-07-07 22:20:19] VFS update request failed (GDRIVE/READING/웹소설/단행): <urlopen error [Errno -2] Name or service not known>
```

## 영향도

- **영향 범위**: 스케줄러 기반 자동 스캔 시 VFS 캐시 갱신 전체
- **심각도**: 높음 (원격 드라이브 스캔 시 최신 파일 목록 미반영 가능)
- **재현 조건**: 라이브러리별 `rclone_rc_url`이 설정된 상태에서 스케줄러 스캔 실행

## 원인 분석

VFS 새로고침 로직이 두 곳에 존재하며 RC URL 조회 방식이 불일치:

| 항목 | `vfs.py` (단일 도서 스캔) | `scheduler_service.py` (스케줄러 스캔) |
|---|---|---|
| RC URL 조회 | 라이브러리별 `rclone_rc_url` 우선 → 전역 설정 폴백 | **전역 설정만 조회** |
| 인증 처리 | URL 내 `user:pass@host` Basic Auth 파싱 ✅ | **인증 처리 없음** ❌ |
| 다중 RC URL | 쉼표 구분 다중 URL 지원 ✅ | **단일 URL만 사용** ❌ |

라이브러리별로 설정된 RC URL을 무시하고 전역 설정(또는 기본값 `localhost:5572`)을 사용했기 때문에, 실제 rclone RC 서버 주소와 불일치하여 DNS 해석 실패가 발생.

## 수정사항

### `services/scheduler_service.py`

`vfs.py`의 `trigger_vfs_refresh()` 함수와 동일한 RC URL 조회 패턴으로 통일:

1. **라이브러리별 `rclone_rc_url` 우선 조회** → 없으면 전역 `RCLONE_RC_URL` 폴백
2. **URL 내 인증 정보(`user:pass@host`) 파싱** 및 Basic Auth 헤더 자동 적용
3. **쉼표 구분 다중 RC URL 지원** (복수 rclone 서버 환경 대응)
4. **로그 내 인증 정보 마스킹** (`****:****@host` 형태로 출력)
5. **DB 커넥션 안전한 해제** (finally 블록 적용)

## 해결 확인

- 스케줄러 스캔 실행 시 라이브러리별 RC URL을 정상적으로 읽어 VFS 캐시 갱신 성공 확인 필요
- `vfs.py`와 `scheduler_service.py` 양쪽 모두 동일한 RC URL 조회 로직 사용
