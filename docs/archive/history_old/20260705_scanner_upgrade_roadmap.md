# 스캐너 고도화 로드맵

이 문서는 외부에서 작성된 스캐너 업그레이드 초안을 현재 코드베이스 기준으로 재해석한 구현 로드맵입니다. 핵심 목표는 스캐너 내부에 분산되어 있는 메타데이터 파싱과 커버 추출 규칙을 플러그인형 구조로 정리하고, 기존 동작과의 호환성을 유지한 채 점진적으로 교체하는 것입니다.

## 1. 현재 상태 분석

현재 스캐너는 메타데이터 처리 책임이 여러 지점에 흩어져 있습니다.

- 로컬 메타데이터 파싱은 [tools/scanner/parser.py](../../tools/scanner/parser.py) 에 집중되어 있습니다.
- 폴더 단위 스캔은 [tools/scanner/tasks.py](../../tools/scanner/tasks.py) 에서 `kavita.yaml`, `info.xml`, `series.json`, `ComicInfo.xml` 조합을 직접 처리합니다.
- 단일 도서 재스캔은 [services/book_scan_service.py](../../services/book_scan_service.py) 에서 별도 경로로 처리합니다.
- 외부 메타데이터 검색 플러그인은 이미 [plugins/metadata/base.py](../../plugins/metadata/base.py) 와 [services/metadata_factory.py](../../services/metadata_factory.py) 로 분리돼 있습니다.

즉, 새 로드맵의 핵심은 완전히 새 시스템을 만드는 것보다, 기존 파싱 로직을 공통 인터페이스로 정리하고 호출부를 한 곳으로 모으는 것입니다.

## 2. 구현 목표

1. 메타데이터 파일별 파서를 개별 모듈로 분리한다.
2. 런타임에 사용 가능한 파서를 자동 탐색하고 캐싱하는 로더를 둔다.
3. 폴더 메타데이터 병합 규칙을 명시적으로 정리한다.
4. 커버 추출과 오프셋 수집의 책임 경계를 분리한다.
5. 기존 스캔 결과와의 호환성을 유지한다.

## 3. 권장 아키텍처

새 구조는 다음처럼 잡는 것이 가장 안전합니다.

```text
tools/scanner/
  metadata/
    __init__.py
    kavita_yaml.py
    series_json.py
    comicinfo_xml.py
    folder_image.py
```

- `kavita_yaml.py`는 YAML 기반 텍스트 메타와 Base64 커버 맵을 담당합니다.
- `series_json.py`는 웹툰용 JSON 메타와 원격 커버 URL을 담당합니다.
- `comicinfo_xml.py`는 CBZ/ZIP 내부 ComicInfo.xml 파싱을 담당합니다.
- `folder_image.py`는 `cover.jpg`, `folder.png` 같은 폴더 공용 이미지만 담당합니다.
- `__init__.py`는 파서 자동 로드, 우선순위 정리, 결과 병합을 담당합니다.

이 구조는 현재 [tools/scanner/parser.py](../../tools/scanner/parser.py) 의 기능을 잘게 나누는 형태라서, 교체 리스크가 낮습니다.

## 4. 단계별 구현 계획

### Phase 1. 파서 분리

- `tools/scanner/parser.py`의 함수들을 파일별 모듈로 이동한다.
- 기존 반환 스키마를 유지한다.
- `cover_b64_map`, `is_webtoon`, `release_date` 같은 필드는 그대로 보존한다.

### Phase 2. 동적 로더 도입

- `tools/scanner/metadata/__init__.py`에서 `importlib` 기반 자동 로드를 구현한다.
- `TARGET_FILENAME`과 `parse()` 존재 여부로 파서 유효성을 검사한다.
- 파서 간 실패는 예외 전파보다 개별 모듈 격리 로그로 처리한다.

### Phase 3. 호출부 교체

- [tools/scanner/tasks.py](../../tools/scanner/tasks.py) 의 직접 호출을 새 로더 기반 호출로 바꾼다.
- [services/book_scan_service.py](../../services/book_scan_service.py) 의 단일 도서 재스캔 경로도 같은 병합 규칙을 쓰게 맞춘다.
- [tools/lazy_scanner.py](../../tools/lazy_scanner.py) 쪽도 동일 인터페이스를 참조하도록 정리한다.

### Phase 4. 커버/오프셋 책임 분리

- 커버 추출은 메타데이터 파서와 파일 시스템 폴백으로 나눈다.
- ZIP/CBZ 오프셋 수집은 별도 모듈을 유지한다.
- 원격 경로에서는 무거운 압축 내부 탐색을 건너뛰는 기존 정책을 유지한다.

### Phase 5. 검증과 회귀 방지

- `kavita.yaml`, `series.json`, `info.xml`, `ComicInfo.xml` 각각에 대해 샘플 입력을 준비한다.
- 로컬 경로와 원격 경로를 분리해 최소 2개 시나리오를 검증한다.
- 기존 DB 컬럼과 결과 JSON 구조가 바뀌지 않았는지 확인한다.

## 5. 우선순위

1. 파서 분리와 병합 규칙 정리
2. 호출부 교체
3. 커버/오프셋 책임 정리
4. 테스트 샘플과 회귀 검증

## 6. 주의할 점

- 현재 코드에는 이미 외부 메타데이터 플러그인 체계가 있으므로, 로컬 스캐너 플러그인과 혼동하지 않아야 합니다.
- 기존 병합 순서를 바꾸면 결과가 달라질 수 있으므로, 우선순위는 명시적으로 고정해야 합니다.
- 단일 도서 재스캔과 폴더 일괄 스캔의 병합 규칙이 달라지지 않도록 공통 헬퍼를 두는 편이 좋습니다.

## 7. 완료 기준

- 새 파서 추가가 기존 코어 파일 수정 없이 가능해야 합니다.
- 기존 스캔 결과와 DB 업데이트 결과가 유지돼야 합니다.
- 원격 마운트와 로컬 파일 시스템 모두에서 예외 없이 동작해야 합니다.
- 커버 추출과 오프셋 수집이 회귀 없이 통과해야 합니다.