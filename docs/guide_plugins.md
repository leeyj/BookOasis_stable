# 🧩 메타데이터 플러그인 개발 가이드 (Metadata Plugin Guide)

이 문서는 BookOasis 미디어 서버의 코어 소스코드를 수정하지 않고 외부 API(예: Google Books, Amazon 등)를 연동하는 새로운 메타데이터 검색 플러그인을 개발하여 추가하는 방법을 다룹니다.

> 주의: 이 문서는 `plugins/metadata/` 아래의 외부 검색 플러그인 가이드입니다. 스캐너 내부에서 파일을 읽고 파싱하는 로컬 파서 개발은 [스캐너 파서 개발 가이드](./guide_scanner_parser.md)를 따르십시오.

---

## 1. 신규 플러그인 생성 방법

### 1) 프로바이더 파일 생성
`plugins/metadata/` 디렉토리에 새로운 파이썬 파일(예: `google.py`)을 생성하십시오. 파일명은 플러그인의 고유 ID 모듈명으로 사용됩니다.

### 2) 프로바이더 클래스 작성
작성할 클래스는 반드시 [plugins/metadata/base.py](../plugins/metadata/base.py)의 `BaseMetadataProvider` 인터페이스 클래스를 상속받아야 합니다.
클래스명은 파일명을 카멜케이스(CamelCase)로 조합하여 `{파일명}MetadataProvider` 형태여야 합니다.
* 예: `google.py` -> `GoogleMetadataProvider`

---

## 2. UI 및 설정 스키마 정의 (config_schema)

플러그인이 브라우저의 **환경설정 > 플러그인 설정** 화면에 자동으로 노출되고 설정을 입력받으려면 아래 클래스 필드들을 정의해 주어야 합니다.

* `id` (str): 고유 식별자 (보통 파일명과 동일 설정)
* `name` (str): 사용자 화면에 표시될 한글/영문 플러그인 이름
* `is_searchable` (bool): 도서 상세 정보 팝업 내 메타데이터 수동 매칭 검색기에서 드롭다운 옵션으로 자동 제공할지 여부
* `config_schema` (list): UI 폼에서 입력받을 필드들의 상세 스펙 정의

### 💡 복합 JSON 설정 값 로직
입력 폼에 설정된 데이터는 하나의 JSON 문자열로 자동 직렬화(Serialize)되어 데이터베이스 `settings` 테이블에 키(`PLUGIN_CONFIG_{id}`)로 매핑 저장됩니다. 따라서 임의의 복잡한 입력 형태도 데이터 소실 없이 직관적으로 보관 및 복구할 수 있습니다.

**지원 폼 종류:**
* `text` / `password` / `number`: 텍스트 및 패스워드, 숫자 폼
* `checkbox`: 불리언 (True / False) 토글 스위치 폼
* `select`: 드롭다운 목록 선택 폼 (`options` 배열 정의 필수)

**config_schema 예시:**
```python
config_schema = [
    {"key": "API_KEY", "label": "API Key", "type": "password", "required": True},
    {"key": "MAX_RETRIES", "label": "최대 재시도 횟수", "type": "number", "default": 3},
    {"key": "SERVER_REGION", "label": "지역", "type": "select", "options": [
        {"value": "us", "label": "미국 (US)"},
        {"value": "kr", "label": "한국 (KR)"}
    ]}
]
```

---

## 3. 필수 인터페이스 메서드 구현

플러그인 클래스 내부에 다음 두 가지 핵심 메서드를 반드시 오버라이드하여 구현해야 합니다.

### 1) `search(self, db_type, query)`
* **역할**: 외부 API 등을 질의하여 검색에 매칭되는 책 후보군 리스트를 조회합니다.
* **인자**: 
  * `db_type` (str): `'prod'` (운영) 또는 `'dev'` (개발)
  * `query` (str): 검색어 (도서 제목 등)
* **리턴값**: `list[dict]` (아래 규격을 만족하는 도서 딕셔너리 목록)
  ```python
  results = [
      {
          'title': '도서 제목',
          'author': '저자명',
          'publisher': '출판사명',
          'pubDate': '출간일(YYYY-MM-DD)',
          'cover': '표지 이미지 원본 URL',
          'description': '책 소개 상세글 내용',
          'link': '해당 도서의 외부 상세정보 연결 URL'
      }
  ]
  ```

### 2) `apply(self, db_type, book_id, item_data)`
* **역할**: 사용자가 수동 매칭 목록에서 특정 도서를 골라 "적용"을 눌렀을 때 실행되며, 책의 표지 이미지를 로컬에 다운로드하고 DB 레코드를 최종 업데이트합니다.
* **인자**:
  * `db_type` (str): DB 환경 구분자
  * `book_id` (int): 변경 대상 도서 레코드 고유 ID
  * `item_data` (dict): 사용자가 고른 `search` 결과 단일 딕셔너리 객체
* **리턴값**: `tuple[bool, str]` - `(성공여부, 반환 메시지)`

---

## 4. 플러그인 템플릿 코드 예시

```python
# -*- coding: utf-8 -*-
import json
import database
from plugins.metadata.base import BaseMetadataProvider

class GoogleMetadataProvider(BaseMetadataProvider):
    id = "google"
    name = "Google Books"
    is_searchable = True
    config_schema = [
        {"key": "GOOGLE_API_KEY", "label": "Google API Key", "type": "text", "required": True}
    ]

    def _get_api_key(self, db_type):
        """DB에 저장된 플러그인 JSON 설정에서 API 키 복원 추출"""
        try:
            conn = database.get_connection(db_type)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'PLUGIN_CONFIG_google'")
            row = cursor.fetchone()
            conn.close()
            if row and row['value']:
                return json.loads(row['value']).get('GOOGLE_API_KEY')
        except Exception:
            pass
        return None

    def search(self, db_type, query):
        api_key = self._get_api_key(db_type)
        if not api_key or not query:
            return []
        
        # 외부 API 연동 수행...
        return []

    def apply(self, db_type, book_id, item_data):
        # 다운로드 및 books 테이블 UPDATE문 수행...
        return True, "적용 성공"
```

---

## 5. 플러그인 등록 및 활성화 프로세스

1. 작성한 파이썬 파일을 `plugins/metadata/` 폴더에 복사합니다.
2. BookOasis 미디어 서버 서비스를 재시작합니다.
3. 웹 브라우저로 접속한 뒤 **환경설정 > 플러그인 설정** 탭에 이동하면 목록에 신규 플러그인이 나타납니다.
4. 토글 스위치로 플러그인을 **활성화(ON)** 상태로 변경하고, 요청된 API Key 등 필수 정보를 입력한 후 저장 버튼을 클릭합니다.
5. `is_searchable = True` 인 경우, 도서 상세 정보 보기 화면 내 "수동 메타데이터 매칭" 검색 모달 드롭다운 목록에서 바로 사용할 수 있습니다.
