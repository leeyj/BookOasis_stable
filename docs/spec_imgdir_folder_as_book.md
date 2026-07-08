# 이미지 폴더를 하나의 도서로 인식하는 기능 설계

> 작성일: 2026-07-08  
> 최종 수정: 2026-07-08  
> 상태: 재검토 중 (수정안 반영)

---

## 배경 및 목적

현재 스캐너는 `/폴더/*.zip`, `/폴더/*.cbz` 등 아카이브 파일을 하나의 도서 단위로 인식한다.  
그러나 일부 콘텐츠는 압축 없이 이미지 파일(`.jpg`, `.png` 등)만 폴더에 그대로 들어있는 경우가 있다.

이 설계는 **이미지 파일만 있는 폴더를 하나의 도서로 인식**하는 기능을 스캐너에 추가하는 방법을 기술한다.

---

## 핵심 설계

### 가상 파일 경로

폴더 자체를 도서로 등록하기 위해 **가상 경로** 방식을 사용한다.

```
DB file_path = 폴더경로/__folder__.imgdir
```

- 실제 파일이 아닌 폴더를 식별하는 가상 식별자
- `__folder__.imgdir` 고정 파일명으로 "이미지 폴더 도서"임을 명확히 구분
- `file_format` 컬럼값: `imgdir` (신규 포맷 타입)

### 안전 가드 (필수)

1. **title 결정 규칙 고정**
  - imgdir 도서의 title은 파일명 기반이 아니라 **폴더명(`os.path.basename(root)`)** 으로 저장한다.
  - 즉, `__folder__.imgdir`는 식별용 file_path 전용이며 title 생성에 사용하지 않는다.

2. **이동 감지 예외 규칙**
  - imgdir 도서는 basename이 모두 `__folder__.imgdir`로 동일해질 수 있으므로,
    basename 기반 자동 이동 감지(rename 매칭) 대상에서 제외한다.
  - 최소 구현: `sync_detector`에서 imgdir(`file_format='imgdir'` 또는 suffix `.imgdir`) 경로는 move 매칭 스킵.

3. **뷰어 미연동 기간 임시 정책**
  - 이번 범위는 DB 등록까지이며, imgdir 뷰어는 후속 작업으로 분리한다.
  - 후속 작업 전까지 UI에서 `imgdir` 열기 시 "지원 예정 포맷" 안내(또는 읽기 버튼 비활성) 정책을 명시 적용한다.

### 처리 분기

| 폴더 상태 | 처리 방식 |
|---|---|
| zip / cbz / epub / pdf / txt 파일 있음 | **기존 방식 유지** |
| 이미지(jpg/png 등)만 있음 | **폴더 전체 = 도서 1개**로 등록 |
| 아무 미디어도 없음 | 스킵 (기존과 동일) |

> **이미지 + zip 혼재 폴더**: zip이 하나라도 있으면 기존 방식 적용, 이미지 폴더 모드 미적용

---

## 도서 정보 구성

| 항목 | 값 |
|---|---|
| `file_path` | `폴더경로/__folder__.imgdir` |
| `file_format` | `imgdir` |
| `title` | **폴더 이름 자체** (예: `1권`, `2권`) |
| `series_name` | **이미지 폴더의 상위 폴더명** (예: `h2`) |
| `cover_image` | 폴더 내 첫 번째 이미지 → WebP 변환 저장 |
| `file_mtime` | 폴더의 mtime |
| `file_size` | 폴더 내 이미지 파일 총 용량 합계 |

---

## 커버 이미지 전략

1. `cover.jpg` / `folder.jpg` 등 공통 커버 파일이 있으면 우선 사용 (기존 `find_common_cover` 활용)
2. 없으면 폴더 내 이미지를 자연 정렬(natural sort) 후 첫 번째 파일을 WebP 변환하여 사용

---

## 수정 대상 파일

### `tools/scanner/tasks.py`

- 상수 추가:
  ```python
  SUPPORTED_IMAGE_FORMATS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
  IMGDIR_VIRTUAL_FILENAME = '__folder__.imgdir'
  ```
- `process_folder_task()`:
  - `media_files`(zip 등)가 없을 때, 이미지 파일 목록 체크
  - 이미지가 있으면 가상 도서 1개짜리 `results` 반환
  - imgdir 도서 생성 시:
    - `title` 소스는 `filename`이 아니라 `root` 폴더명 사용
    - `series_name`은 상위 폴더명 기준 분기 적용

### `tools/scanner/engine.py`

- `os.walk` 루프:
  - `media_files`가 없어도 이미지 파일이 있으면 `tasks`에 추가
  - `found_file_paths`에 가상 경로(`__folder__.imgdir`) 추가
  - 배치 insert 데이터에 imgdir 전용 `title` 전달 필드(또는 계산 분기) 추가

### `tools/scanner/cover.py`

- `get_imgdir_cover(folder_path, library_id, force)` 함수 추가:
  - `find_common_cover()` → 없으면 첫 번째 이미지 직접 WebP 변환

### `tools/scanner/sync_detector.py`

- basename 기반 이동 감지 로직에서 imgdir 가상 경로 제외 처리

### `static/js/viewer.js` (임시 정책)

- `imgdir` 포맷 진입 시 임시 안내 메시지 처리(지원 예정)
  - 또는 상세 목록에서 읽기 버튼 비활성 처리와 병행

---

## 미결 사항 (고민 필요)

### Q1. 이미지 + zip 혼재 폴더

같은 폴더에 zip 파일과 이미지 파일이 함께 있을 경우:
- **A안**: zip만 처리 (현재 설계)
- **B안**: zip 처리 + 이미지도 별도로 폴더 단위 도서 추가

**결정: A안 채택**

- 중복 등록과 시리즈 정렬 혼선을 줄이기 위해, 동일 폴더에서는 기존 아카이브 우선 정책을 유지한다.

### Q2. 이미지 폴더 + zip 혼재 시리즈 (분석 완료)

```
/도서/만화/h2/1권/*.jpg   → imgdir 도서, series_name = "h2", title = "1권"
/도서/만화/h2/2권/*.jpg   → imgdir 도서, series_name = "h2", title = "2권"
/도서/만화/h2/3권.zip     → zip 도서,    series_name = "h2", title = "3권"
```

**가능하다.** 단, imgdir 도서 생성 시 series_name 결정 방식이 달라야 한다.

| 도서 타입 | series_name 결정 방식 | 코드 |
|---|---|---|
| zip / epub 등 | `root` 폴더명 (현재 방식 유지) | `path_parts[-1]` |
| imgdir (이미지 폴더) | **이미지 폴더의 상위 폴더명** | `os.path.basename(os.path.dirname(root))` |

> **핵심**: imgdir 도서는 `title = 폴더명(1권)`, `series_name = 상위폴더명(h2)` 으로 설정해야 zip 도서와 같은 시리즈로 묶인다.

### Q3. 서브폴더로만 분권된 경우

```
시리즈명/
  1권/001.jpg, 002.jpg, ...
  2권/001.jpg, 002.jpg, ...
```

- **현재 설계**: 각 서브폴더(`1권/`, `2권/`)를 도서 1개씩 → 자동 처리됨
- 별도 처리 없이 `os.walk`가 각 폴더를 순회하므로 자연스럽게 동작

### Q4. 뷰어 연동

`imgdir` 포맷 도서를 열었을 때 이미지 파일들을 순서대로 보여주는 뷰어 연동이 필요하다.  
현재 뷰어는 zip 내부 이미지를 offset 기반으로 읽는 방식이므로, `imgdir` 전용 처리 로직이 추가로 필요하다.

> **이번 범위**: 스캐너가 도서를 인식하고 DB에 등록하는 것까지.  
> 뷰어 연동은 별도 작업으로 분리.

임시 운영 정책:
- `imgdir`는 스캔/등록/커버 표시까지만 지원
- 열기 시 사용자에게 "뷰어 지원 예정" 안내를 노출

### Q5. 변경 감지 (스킵 로직)

이미지 폴더 도서의 변경 감지:
- `file_mtime`을 폴더의 mtime으로 저장
- 폴더 mtime이 바뀌지 않으면 스킵

---

## 검증 계획

1. 이미지 파일만 있는 테스트 폴더 생성 후 스캔
2. DB에 `file_format = 'imgdir'` 도서가 등록되는지 확인
3. 커버 이미지가 첫 번째 이미지에서 추출되는지 확인
4. 기존 zip/epub 폴더가 영향 없는지 확인
5. 혼재 폴더(zip + jpg)에서 zip만 처리되는지 확인
6. imgdir 도서의 `title`이 `__folder__`가 아닌 실제 폴더명으로 저장되는지 확인
7. imgdir 도서 `series_name`이 상위 폴더명으로 저장되어 zip 권과 같은 시리즈로 묶이는지 확인
8. 파일 이동/이름변경 시 imgdir가 basename 충돌로 오탐 매칭되지 않는지 확인
9. 커버 재생성(cover-only 경로)에서 imgdir 가상 경로가 아닌 폴더 기준으로 정상 동작하는지 확인
10. UI에서 imgdir 열기 시 임시 안내(또는 비활성) 정책이 의도대로 노출되는지 확인
