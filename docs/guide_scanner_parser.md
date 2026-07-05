# 🧩 스캐너 파서 개발 가이드 (Scanner Parser Development Guide)

이 문서는 `tools/scanner/metadata/` 계열의 로컬 메타데이터 파서 모듈을 작성하거나 수정할 때 따라야 하는 규칙을 정리합니다. 외부 검색 플러그인([guide_plugins.md](./guide_plugins.md))과는 목적이 다르며, 스캐너가 파일 시스템에서 직접 읽는 로컬 파서에만 적용됩니다.

---

## 1. 기본 원칙

### 1) 파서는 자급형이어야 합니다
각 파서 파일은 다른 파서 모듈이나 [tools/scanner/parser.py](../tools/scanner/parser.py) 에 의존하지 않고, 필요한 유틸을 해당 파일 안에 직접 포함해야 합니다.

### 2) 직접 호출은 금지합니다
새로운 코드에서는 [tools/scanner/parser.py](../tools/scanner/parser.py) 를 공용 헬퍼처럼 직접 import해서 쓰지 마십시오.

- 허용: [tools/scanner/metadata/__init__.py](../tools/scanner/metadata/__init__.py) 를 통한 공통 진입
- 허용: [tools/scanner/metadata/info_xml.py](../tools/scanner/metadata/info_xml.py), [tools/scanner/metadata/kavita_yaml.py](../tools/scanner/metadata/kavita_yaml.py), [tools/scanner/metadata/series_json.py](../tools/scanner/metadata/series_json.py), [tools/scanner/metadata/comicinfo_xml.py](../tools/scanner/metadata/comicinfo_xml.py)
- 허용: `komga_yaml.py` 같은 새 폴더형 파서는 `tools/scanner/metadata/` 에 파일을 추가하면 자동 반영됨
- 금지: 새 파서 코드에서 [tools/scanner/parser.py](../tools/scanner/parser.py) 의 함수에 의존하는 방식

### 3) 레거시 parser.py 는 호환성 용도입니다
[tools/scanner/parser.py](../tools/scanner/parser.py) 는 기존 호출부 호환을 위한 레거시 모듈로만 취급합니다. 신규 기능 추가는 우선적으로 `tools/scanner/metadata/` 쪽에서 진행합니다.

---

## 2. 모듈 작성 규칙

### 1) 필수 인터페이스
각 모듈은 다음 항목을 갖춰야 합니다.

- `TARGET_FILENAME`: 탐지 대상 파일명
- `parse(target_path, is_remote=False)`: 단일 진입 함수

폴더 스캔에서 파일 목록 기반으로 더 세밀한 처리가 필요하면 `parse_<name>(folder_path, files=None, is_remote=False)` 같은 보조 함수를 둘 수 있습니다.

### 2) 반환 스키마
반환값은 가능하면 기존 스캐너 병합 로직과 호환되는 딕셔너리 형태여야 합니다.

- 텍스트 메타: `author`, `publisher`, `summary`, `link`, `score`, `release_date`, `genre`, `tags`
- 표지 관련: `cover_b64_map`, `cover_image_url`
- 상태값: `is_webtoon`, `has_yaml`

### 3) 예외 처리
- 파일이 없거나 읽을 수 없으면 예외를 바깥으로 던지기보다 빈 메타를 반환합니다.
- 원격 경로는 I/O 비용이 크므로, 타임아웃 또는 안전한 스킵을 기본으로 둡니다.

---

## 3. 권장 분리 기준

### 1) `info_xml.py`
`info.xml` 텍스트 메타를 담당합니다.

### 2) `kavita_yaml.py`
`kavita.yaml` 텍스트 메타와 Base64 표지 맵을 담당합니다.

### 3) `series_json.py`
웹툰용 `series.json` 메타와 원격 표지 URL을 담당합니다.

### 4) `comicinfo_xml.py`
CBZ/ZIP 내부의 `ComicInfo.xml` 메타를 담당합니다.

### 5) `folder_image.py`
`cover.jpg`, `folder.png` 같은 폴더 공용 이미지만 담당합니다.

### 6) 새 포맷 예시: `komga_yaml.py`

- 파일명: `komga_yaml.py`
- 대상 파일명: `komga.yaml`
- 구현: `TARGET_FILENAME` 와 `parse()` 만 준비하면 됩니다.
- 주의: 이 가이드는 폴더 메타데이터용입니다. ZIP/CBZ 내부 메타처럼 파일 내부를 여는 로직은 별도 파일 단위 처리 경로를 사용합니다.

아래는 그대로 복사해서 시작할 수 있는 최소 예시입니다.

```python
# -*- coding: utf-8 -*-
import html
import os
import re
import threading
import time

import yaml

TARGET_FILENAME = "komga.yaml"

HTML_TAG_RE = re.compile(r'<[^>]*>')


class NetworkCircuitBreaker:
    def __init__(self, max_failures=3, reset_timeout=60):
        self.failures = 0
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self._lock = threading.Lock()

    def is_tripped(self):
        with self._lock:
            if self.failures >= self.max_failures:
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.failures = 0
                    return False
                return True
            return False


_circuit_breaker = NetworkCircuitBreaker()


def clean_html_tags(text):
    if not text:
        return ''
    return html.unescape(HTML_TAG_RE.sub('', text)).strip()


def read_file_with_timeout(file_path, is_remote, timeout=10):
    if not is_remote:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None

    if _circuit_breaker.is_tripped():
        return None

    result = []

    def _read():
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                result.append(f.read())
        except Exception as e:
            result.append(e)

    thread = threading.Thread(target=_read)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    if not result or thread.is_alive():
        return None
    if isinstance(result[0], Exception):
        return None
    return result[0]


def parse(target_path, is_remote=False):
    return parse_komga_yaml(target_path, is_remote=is_remote)


def parse_komga_yaml(folder_path, files=None, is_remote=False):
    meta = {
        'author': '',
        'publisher': '',
        'summary': '',
        'link': '',
        'score': 0,
        'release_date': '',
        'genre': '',
        'tags': '',
        'cover_b64_map': {},
        'cover_image_url': '',
        'is_webtoon': False,
        'has_yaml': False,
    }

    yaml_path = os.path.join(folder_path, 'komga.yaml')
    has_yaml = False
    actual_yaml_path = yaml_path

    if files is not None:
        for f in files:
            if f.lower() == 'komga.yaml':
                has_yaml = True
                actual_yaml_path = os.path.join(folder_path, f)
                break
    else:
        if os.path.exists(yaml_path):
            has_yaml = True

    if not has_yaml:
        return meta

    meta['has_yaml'] = True

    try:
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import SafeLoader

    content = read_file_with_timeout(actual_yaml_path, is_remote)
    if content is None:
        return meta

    data = yaml.load(content, Loader=SafeLoader) or {}

    if isinstance(data, dict):
        meta['author'] = data.get('author', '') or data.get('writer', '')
        meta['publisher'] = data.get('publisher', '')
        meta['summary'] = clean_html_tags(data.get('description', '') or data.get('summary', ''))
        meta['link'] = data.get('link', '')
        meta['score'] = data.get('score', 0) or 0
        meta['release_date'] = data.get('release_date', '')
        meta['genre'] = data.get('genre', '')
        tags = data.get('tags', '')
        if isinstance(tags, list):
            meta['tags'] = ', '.join(str(item).strip() for item in tags if item)
        else:
            meta['tags'] = str(tags).strip()

        files_node = data.get('files', {})
        if isinstance(files_node, dict):
            for filename, item in files_node.items():
                if isinstance(item, dict) and item.get('cover'):
                    meta['cover_b64_map'][filename] = item['cover']

    return meta
```

### 사용 예시

1. 위 코드를 `tools/scanner/metadata/komga_yaml.py` 로 저장합니다.
2. 같은 폴더에 `komga.yaml` 이 존재하면 자동으로 로드됩니다.
3. 텍스트 메타는 기존 병합 규칙에 맞춰 자동 병합됩니다.
4. 표지 Base64가 있으면 `cover_b64_map` 을 통해 커버 추출 단계에서 활용할 수 있습니다.


## 4. 추가 시 체크 포인트

1. 새 파서는 다른 모듈에서 import하지 않아도 동작해야 합니다.
2. `load_all_parsers()` 에서 자동 로드가 가능해야 합니다.
3. `merge_local_metadata()` 와의 반환 키가 충돌하지 않아야 합니다.
4. 테스트용으로는 최소한 로컬 폴더 1개, 원격 폴더 1개 시나리오를 확인해야 합니다.

---

## 5. 예시

```python
# -*- coding: utf-8 -*-
TARGET_FILENAME = "example.meta"

def parse(target_path, is_remote=False):
    return {
        "author": "",
        "publisher": "",
        "summary": "",
        "link": "",
        "score": 0,
        "release_date": "",
        "genre": "",
        "tags": "",
        "cover_b64_map": {},
        "cover_image_url": "",
        "is_webtoon": False,
        "has_yaml": False,
    }
```