---
title: "OPDS 최근 읽은 도서 제목 손상 오류 수정"
date: 2026-06-25T02:55:30+09:00
category: "Bug Fix"
tags: [opds, title-corruption, filename-extraction]
status: "completed"
---

# 📋 작업 아이템 (Task List)

## 개요
OPDS 피드의 `최근 읽은 도서` 섹션에서 일부 도서 제목이 "1 - 0", "2 - 0" 같은 손상된 값으로 표시되는 문제 해결

## 작업 항목

### 1. ✅ DB 데이터 검증
- **대상**: `media_general.db` / `books` 테이블
- **발견사항**: 
  - 제목이 "1 - 0", "2 - 0", "3 - 0" 등으로 손상된 레코드 다수 존재
  - 파일 경로는 정상: `/home/az001a/google/GDRIVE/READING/만화/완결A/가/김태권의 십자군 이야기/김태권의 십자군 이야기 01권 (예스)#252.zip`
  - 제목이 파싱 실패로 인해 부정확한 상태
- **결론**: 제목 손상은 구형 스캐너 데이터, DB에서는 해결 불가

### 2. ✅ 제목 추출 헬퍼 함수 구현
**파일**: `api/opds.py`

#### 함수 1: `_extract_title_from_path(file_path)`
```python
def _extract_title_from_path(file_path: str) -> str:
    """파일 경로에서 제목 추출 (손상된 제목용 fallback)"""
    if not file_path:
        return ''
    filename = os.path.basename(file_path)
    filename = os.path.splitext(filename)[0]  # 확장자 제거
    filename = re.sub(r'#\d+$', '', filename)  # "#숫자" 제거
    return filename.strip()
```

**예시**:
- Input: `/path/김태권의 십자군 이야기 01권 (예스)#252.zip`
- Output: `김태권의 십자군 이야기 01권 (예스)`

#### 함수 2: `_is_corrupted_title(title)`
```python
def _is_corrupted_title(title: str) -> bool:
    """제목이 손상되었는지 확인 (숫자 - 숫자 패턴)"""
    if not title:
        return False
    return bool(re.match(r'^\d+\s*-\s*\d+$', title.strip()))
```

**패턴 감지**:
- "1 - 0" ✓ (손상됨)
- "2 - 0" ✓ (손상됨)
- "12 - 5" ✓ (손상됨)
- "정상 제목" ✗ (정상)

### 3. ✅ `_recently_read_entries()` 함수 수정
**파일**: `api/opds.py` / 라인 212~246

**변경 내용**:
```python
for i, b in enumerate(books):
    mime = mimetypes.guess_type(b['file_path'])[0] or 'application/octet-stream'
    # 제목이 손상된 경우 파일명에서 추출
    title = b['title']
    if _is_corrupted_title(title):
        title = _extract_title_from_path(b['file_path'])
    entries.append({
        'id'     : f"urn:{urn_prefix}:read:{i}",
        'title'  : title,
        ...
    })
```

### 4. ✅ 코드 임포트 업데이트
**파일**: `api/opds.py` / 라인 10~15

**추가 임포트**:
```python
import re  # 정규식 패턴 매칭
```

### 5. ✅ 문법 검증
```bash
python -m py_compile api/opds.py
# ✓ 에러 없음
```

### 6. ✅ 로컬 테스트
**결과**:
```
Total entries: 30

=== 처음 5개 엔트리 ===

 1. Title: '김태권의 십자군 이야기 01권 (예스)'
 2. Title: '데밀카 님은 강철멘탈 악역 영애 01권 (리디)'
 3. Title: '낙제기사의 영웅담 01권 (리디)'
 4. Title: '낙제기사의 영웅담 01권 (리디)'
 5. Title: '01권'
```

**검증 사항**:
- ✓ 30개 엔트리 정상 로드
- ✓ 제목이 파일명에서 정상 추출됨
- ✓ 커버 이미지 정상 포함

### 7. ✅ 배포
**명령어**: `python deploy.py`

**배포 결과**:
- ✓ 111개 파일 업로드 완료
- ✓ 구형 CSS 파일 3개 삭제
- ✓ 원격 미디어 서버 재구동 (PID: 4160806)
- ✓ 배포 성공

## 변경 파일
1. `api/opds.py`
   - `_extract_title_from_path()` 함수 추가
   - `_is_corrupted_title()` 함수 추가
   - `_recently_read_entries()` 함수 수정 (제목 검증 로직 추가)
   - `import re` 추가

## 사용자 검증
✅ 사용자 확인: "제대로 표시됨을 확인했어"

## 성과
- 🎯 OPDS 피드 최근 읽은 도서 섹션 제목 정상 표시
- 🎯 파일명 기반 폴백 메커니즘으로 DB 손상 데이터 자동 복구
- 🎯 iOS Panels 리더에서 정상 제목 표시 확인
