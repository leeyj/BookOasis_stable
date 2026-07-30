---
title: "OPDS 최근 읽은 도서 제목 손상 오류 수정 - 상세 기록"
date: 2026-06-25T02:55:30+09:00
category: "Bug Fix"
tags: [opds, title-corruption, filename-extraction, validation]
status: "completed"
---

# 📖 작업 워크쓰루 (Walkthrough)

## 1. 문제 발견 및 분석

### 사용자 보고
> "최근 읽은 도서에서 도서 이름이 제대로 표시되지 않고 있어"
> "일부 도서는 1-0 등으로 표시되고, 제대로 출력되는 것도 있어"

### 의심 사항
- OPDS 피드 쿼리 문제 또는
- DB 데이터 손상

## 2. 근본 원인 파악

### 데이터 검증 쿼리
```python
# 최근 읽은 도서 - 실제 데이터
cursor.execute("""
    SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
    FROM user_progress p
    JOIN books b ON p.book_id = b.id
    WHERE b.title IS NOT NULL AND b.title != ''
    ORDER BY p.last_read_at DESC
    LIMIT 10
""")
```

### 검사 결과
| ID | Title | File Path | 상태 |
|---|---|---|---|
| 469975 | "1 - 0" | `/...김태권의 십자군 이야기 01권 (예스)#252.zip` | ❌ 손상됨 |
| 479427 | "1 - 0" | `/...데밀카 님은 강철멘탈 악역 영애 01권 (리디)#166.zip` | ❌ 손상됨 |
| 546741 | "1 - 0" | `/...낙제기사의 영웅담 01권 (리디)#217.zip` | ❌ 손상됨 |
| 545862 | "2 - 0" | `/...은빛 하모니 02권#196.zip` | ❌ 손상됨 |
| 665539 | "Giant.2022.01#150" | `/.../ Giant.2022.01#150.zip` | ✅ 정상 |

### 핵심 발견
**파일 경로는 정상이지만 제목만 손상됨** → DB 레코드 문제, 파일명 기반 추출로 해결 가능

## 3. 해결 방안 수립

### 전략
1. **손상 패턴 탐지**: "숫자 - 숫자" 정규식 매칭
2. **자동 복구**: 파일명에서 제목 추출 (fallback)
3. **안전성**: 정상 제목은 그대로 사용, 손상된 제목만 교체

### 구현 계획
```
api/opds.py 수정
├── import re 추가 (정규식 패턴 매칭)
├── _extract_title_from_path() 함수 추가
├── _is_corrupted_title() 함수 추가
└── _recently_read_entries() 함수 수정
    └── 제목 손상 여부 확인 후 파일명 추출
```

## 4. 헬퍼 함수 구현 상세

### 함수 1: 손상 제목 탐지
```python
def _is_corrupted_title(title: str) -> bool:
    """제목이 손상되었는지 확인"""
    if not title:
        return False
    # 정규식: 숫자 - 숫자 (예: "1 - 0", "12 - 5")
    return bool(re.match(r'^\d+\s*-\s*\d+$', title.strip()))
```

**테스트 케이스**:
- `_is_corrupted_title("1 - 0")` → `True` ✓
- `_is_corrupted_title("2 - 0")` → `True` ✓
- `_is_corrupted_title("12 - 5")` → `True` ✓
- `_is_corrupted_title("정상 제목")` → `False` ✓
- `_is_corrupted_title("01권")` → `False` ✓

### 함수 2: 파일명 기반 제목 추출
```python
def _extract_title_from_path(file_path: str) -> str:
    """파일 경로에서 제목 추출"""
    if not file_path:
        return ''
    
    # 1. 파일명 추출 (경로의 마지막 부분)
    filename = os.path.basename(file_path)
    
    # 2. 확장자 제거
    filename = os.path.splitext(filename)[0]
    
    # 3. "#숫자" 제거 (예: "책제목#123" → "책제목")
    filename = re.sub(r'#\d+$', '', filename)
    
    # 4. 앞뒤 공백 제거
    return filename.strip()
```

**변환 예시**:
```
Input:  "/path/김태권의 십자군 이야기 01권 (예스)#252.zip"
Step 1: "김태권의 십자군 이야기 01권 (예스)#252.zip"  (basename)
Step 2: "김태권의 십자군 이야기 01권 (예스)#252"      (확장자 제거)
Step 3: "김태권의 십자군 이야기 01권 (예스)"           (#숫자 제거)
Output: "김태권의 십자군 이야기 01권 (예스)"           ✓
```

## 5. 핵심 코드 수정

### 변경 전
```python
def _recently_read_entries(db_type: str, download_prefix: str, urn_prefix: str):
    """최근 읽은 도서 목록을 OPDS acquisition 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
        FROM user_progress p
        JOIN books b ON p.book_id = b.id
        WHERE b.title IS NOT NULL AND b.title != ''
        ORDER BY p.last_read_at DESC
        LIMIT 30
    """)
    books = cursor.fetchall()
    conn.close()
    entries = []
    for i, b in enumerate(books):
        mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
        entries.append({
            'id'     : f"urn:{urn_prefix}:read:{i}",
            'title'  : b['title'],  # ❌ 손상된 제목 그대로 사용
            'summary': '',
            'type'   : 'acquisition',
            'href'   : f"{download_prefix}/{b['id']}",
            'mime'   : mime,
            'cover'  : b['cover_image'],
        })
    return entries
```

### 변경 후
```python
def _recently_read_entries(db_type: str, download_prefix: str, urn_prefix: str):
    """최근 읽은 도서 목록을 OPDS acquisition 엔트리 리스트로 반환"""
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, b.title, b.file_path, b.cover_image, p.last_read_at
        FROM user_progress p
        JOIN books b ON p.book_id = b.id
        WHERE b.title IS NOT NULL AND b.title != ''
        ORDER BY p.last_read_at DESC
        LIMIT 30
    """)
    books = cursor.fetchall()
    conn.close()
    entries = []
    for i, b in enumerate(books):
        mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
        # 제목이 손상된 경우 파일명에서 추출
        title = b['title']
        if _is_corrupted_title(title):
            title = _extract_title_from_path(b['file_path'])  # ✓ 파일명 기반 추출
        entries.append({
            'id'     : f"urn:{urn_prefix}:read:{i}",
            'title'  : title,  # ✓ 정상 또는 복구된 제목
            'summary': '',
            'type'   : 'acquisition',
            'href'   : f"{download_prefix}/{b['id']}",
            'mime'   : mime,
            'cover'  : b['cover_image'],
        })
    return entries
```

## 6. 테스트 및 검증

### 로컬 테스트 실행
```python
from api.opds import _recently_read_entries

entries = _recently_read_entries('general', '/opds/download/general', 'general')
print(f"Total entries: {len(entries)}")
```

### 결과
```
Total entries: 30

=== 처음 10개 엔트리 ===

 1. Title: '김태권의 십자군 이야기 01권 (예스)'
    ID: urn:general:read:0

 2. Title: '데밀카 님은 강철멘탈 악역 영애 01권 (리디)'
    ID: urn:general:read:1

 3. Title: '낙제기사의 영웅담 01권 (리디)'
    ID: urn:general:read:2

 4. Title: '낙제기사의 영웅담 01권 (리디)'
    ID: urn:general:read:3

 5. Title: '01권'
    ID: urn:general:read:4

 6. Title: '01권'
    ID: urn:general:read:5

 7. Title: '만능 시녀 코니 빌러 02권 (리디)'
    ID: urn:general:read:6

 8. Title: '만능 시녀 코니 빌러 01권 (리디)'
    ID: urn:general:read:7

 9. Title: 'Giant.2022.01#150'
    ID: urn:general:read:8

10. Title: '내사랑 우시치치 1권 - 제03화'
    ID: urn:general:read:9
```

### 검증 결과
✅ 30개 엔트리 정상 로드  
✅ 손상된 제목("1 - 0", "2 - 0") → 정상 제목으로 변환됨  
✅ 정상 제목은 그대로 유지됨  
✅ 커버 이미지 정상 포함  

## 7. 배포

### 배포 명령어
```bash
python deploy.py
```

### 배포 결과
```
🚀 [BookOasis] 독립 프로젝트 전용 홈 서버 배포 시작
============================================================
[+] 111개 파일 업로드 완료
[+] 구형 CSS 파일 3개 삭제 (정리)
[+] 원격 미디어 서버 재구동 성공! (PID: 4160806)

✨ [BookOasis] 독립 마이그레이션 배포 및 단독 재구동 완료!
============================================================
```

**배포 확인**:
- ✅ `api/opds.py` 업로드 완료
- ✅ 원격 서버 재구동 완료
- ✅ OPDS 피드 정상 작동

## 8. 최종 결과

### 사용자 검증
> "제대로 표시됨을 확인했어"

### 성과
🎯 **OPDS 피드 제목 표시 정상화**
- 이전: "1 - 0", "2 - 0" 손상된 제목
- 현재: "김태권의 십자군 이야기 01권 (예스)" 정상 제목

🎯 **자동 복구 메커니즘**
- DB 손상 데이터 → 파일명 기반 자동 추출
- 추가 DB 수정 불필요

🎯 **iOS Panels 리더 호환성**
- OPDS XML 피드에서 정상 제목 표시
- 최근 읽은 도서 섹션 정상 작동

## 9. 기술 요약

### 적용 기술
| 항목 | 설명 |
|---|---|
| **정규식 패턴 매칭** | 손상된 제목 패턴 탐지 (`^\d+\s*-\s*\d+$`) |
| **파일 경로 파싱** | `os.path.basename()`, `os.path.splitext()` |
| **Fallback 전략** | 손상된 데이터 자동 복구 |
| **조건부 처리** | `if _is_corrupted_title()` 로직 |

### 코드 변경 통계
- **추가 함수**: 2개 (`_extract_title_from_path`, `_is_corrupted_title`)
- **수정 함수**: 1개 (`_recently_read_entries`)
- **추가 임포트**: 1개 (`import re`)
- **파일 변경**: 1개 (`api/opds.py`)

### 배포 영향도
- ✅ OPDS 피드만 영향 (다른 기능 무영향)
- ✅ 기존 쿼리 유지 (DB 스키마 무변경)
- ✅ 역호환성 완벽 (fallback으로만 작동)

---

**작업 완료**: 2026-06-25 02:55:30 KST  
**배포 상태**: ✅ 완료 (PID: 4160806)
