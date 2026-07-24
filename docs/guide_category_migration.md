---
title: "CLI 카테고리 내보내기/가져오기 및 병합 도구 가이드 (네이티브 & 도커 완벽 대응)"
category: "guide"
date: 2026-07-24
tags: [cli, export, import, merge, migration, backup, multi-path, batch, zip_stored, docker, inspect]
---

# 📦 카테고리 내보내기/가져오기 및 병합 CLI 도구 가이드 (`export_category.py` / `import_category.py`)

이 도구는 외부 메타데이터 검색(알라딘/네이버 등) 및 뷰어 스트리밍 offset 재계산 없이, 카테고리의 모든 DB 메타데이터와 커버 이미지를 타 시스템/백업본으로 초고속 이관하거나 **기존 운영 중인 카테고리에 1초 만에 통합/병합(Merge)**할 수 있는 독립 CLI 전용 유틸리티입니다.  
**네이티브 환경은 물론 도커(Docker / Docker-Compose) 환경도 완벽 대응합니다.**

---

## 🔍 0. 패키지 검사 및 병합 가능 카테고리 미리보기 (`--info` / `--inspect`)

백업 패키지(`.oasis.zip`)의 내부 구성(원본 경로 수, 도서 수, 표지 수)과 **현재 DB에 존재하는 기존 카테고리 목록(ID, 이름, 물리 경로)**을 사전에 한눈에 확인할 수 있습니다.

```bash
# 네이티브 환경
python tools/import_category.py -i 백업파일.oasis.zip --info

# 도커 환경
docker exec -it bookoasis python tools/import_category.py -i /app/covers/백업파일.oasis.zip --info
```

### **미리보기 리포트 출력 예시**:
```text
==========================================================
📦 [BookOasis Package Inspection Info]
==========================================================
  • Category Name : 가정_살림(GDS)
  • DB Type       : general
  • Total Books   : 2351 items
  • Total Covers  : 2351 files
  • Original Physical Paths Count : 2 entries
    [0] /home/az001a/google/GDRIVE/READING/책/YES24 북클럽/가정 살림
    [1] /home/az001a/google/GDRIVE/READING/책/리디셀렉트/가정.생활
==========================================================
👉 Import Recommendations:
   1) 신규 카테고리로 가져오기:
      python tools/import_category.py -i "백업파일.oasis.zip" -p "/path/to/target" -n "새 이름"
   2) 기존 카테고리에 병합(Merge)하기:
      python tools/import_category.py -i "백업파일.oasis.zip" --merge-to <카테고리ID 또는 이름> -p "/path/to/target"
==========================================================

📂 [Existing DB Categories Available for Merging (--merge-to)]
----------------------------------------------------------
  • [GENERAL] ID 15  | 이름: '만화_완결보관함' (경로: /mnt/gdrive/만화A)
  • [GENERAL] ID 18  | 이름: '소설_컬렉션' (경로: /mnt/gdrive/소설)
  • [ADULT]   ID 3   | 이름: '성인_보관함' (경로: /mnt/gdrive/성인)
----------------------------------------------------------
```

---

## ⚡ 패키징 성능 최적화 (`ZIP_STORED`)
- 이미 압축된 이미지 바이너리(WebP, JPG, PNG)는 zlib 재압축 시 용량 절감 이득이 0%이므로, 불필요한 CPU 점유와 소요 시간을 방지하기 위해 **`zipfile.ZIP_STORED` (무압축 스토어/단순 묶음)** 방식을 사용합니다.
- 이에 따라 **CPU 부하 0%**, **디스크 I/O 속도 그대로 수초 만에 초고속으로 아카이빙**이 완료됩니다.

---

## 💻 1. 네이티브(Native) 환경 사용 가이드

### **가) 카테고리 내보내기 (`export_category.py`)**
```bash
# 단일 카테고리 내보내기
python tools/export_category.py --db general -l 21

# 다중 카테고리 한 번에 일괄 내보내기 (Batch Export)
python tools/export_category.py --db general -l 15 18 21 -o /backups/
```

### **나) 카테고리 신규 가져오기 (`import_category.py`)**
```bash
# 단일 경로 신규 가져오기
python tools/import_category.py -i /backups/manga_21.oasis.zip -p "/volume1/mnt/GDDRIVE/READING/만화/완결A" -n "이관된 만화보관함"

# N개 다중 경로 신규 가져오기 (-p 옵션 5개, 8개 등 개수 제한 없음)
python tools/import_category.py \
  -i /backups/novel_export.oasis.zip \
  -p "/volume1/mnt/GDRIVE/READING/책/YES24 북클럽/소설" \
  -p "/volume1/mnt/GDRIVE/READING/책/리디셀렉트/가정.생활" \
  -n "가정_살림(GDS)"
```

### **다) 기존 카테고리에 합치기/병합 (`--merge-to` / `-m`)** ⭐ **[NEW]**
독립된 신규 카테고리를 만들지 않고, **기존 운영 중인 카테고리(예: ID 15번 '소설')로 1초 만에 통합/병합**합니다.

> [!NOTE]
> **도서 식별 및 중복 처리 원칙**:
> - 도서 제목이 완전히 동일하더라도 디스크 상의 전체 파일 경로(`file_path`)가 다르면 **서로 다른 독립된 별개의 도서**로 인식하여 각각 개별 등록됩니다.
> - 디스크 상의 `file_path`가 100% 일치하는 동일 파일일 때만 중복으로 판정하여 자동 스킵(Skip)합니다.

```bash
# 1) 카테고리 ID를 지정하여 병합
python tools/import_category.py \
  -i /backups/novel_part2.oasis.zip \
  --merge-to 15 \
  -p "/volume1/mnt/GDRIVE/READING/소설B"

# 2) 카테고리 이름을 지정하여 병합
python tools/import_category.py \
  -i /backups/novel_part2.oasis.zip \
  --merge-to "판타지 소설" \
  -p "/volume1/mnt/GDRIVE/READING/소설B"
```

---

## 🐳 2. 도커 (Docker / Docker Compose) 환경 사용 가이드

호스트 OS에 파이썬이 설치되어 있지 않아도, `docker exec` 명령어를 통해 실행 중인 BookOasis 컨테이너 내부 파이썬 환경에서 즉시 실행 가능합니다.

> [!TIP]
> **💡 도커 사용자 헷갈림 방지 핵심 공식**:
> `[웹 UI의 카테고리 관리에서 입력하는 경로]  <─── 100% 동일 ───>  [-p 옵션 경로]`

### **가) 도커 환경 내보내기 (Export)**
```bash
# Docker 사용 시 (컨테이너 이름: bookoasis 가정)
docker exec -it bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip

# Docker Compose 사용 시
docker-compose exec bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip
```

### **나) 도커 환경 가져오기 및 기존 카테고리 병합 (Import / Merge)**

#### **1) 신규 카테고리로 가져오기**
```bash
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/manga_21.oasis.zip \
  -p "/volume1/mnt/GDDRIVE/READING/만화/완결A" \
  -n "이관된 만화 보관함"
```

#### **2) 기존 카테고리에 병합(Merge)하기** ⭐ **[NEW]**
```bash
# 기존 카테고리 ID 15번에 병합하여 가져오기
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  --merge-to 15 \
  -p "/volume1/mnt/GDRIVE/READING/소설_파트2"

# Docker Compose 환경에서 기존 카테고리 이름으로 병합하기
docker-compose exec bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  --merge-to "판타지 소설" \
  -p "/volume1/mnt/GDRIVE/READING/소설_파트2"
```

---

## 🔒 핵심 기능 정리
1. **기존 카테고리 병합 (`--merge-to` / `-m`)**: 신규 생성 대신 기존 카테고리(ID 또는 이름)로 1초 만에 원클릭 통합.
2. **패키지 미리보기 & DB 카테고리 리포트 (`--info`)**: 복원 전 원본 경로 구조 및 병합 가능한 기존 DB 카테고리 목록 사전에 확인.
3. **Docker / Docker-Compose 완전 대응**: `docker exec` 명령어로 온프레미스/클라우드 컨테이너 환경 완벽 지원.
4. **초고속 `ZIP_STORED` 패키징**: 이미지 재압축 생략으로 CPU 점유 0%, 수 초 내 대용량 패키징 완수.
5. **다중 물리 경로(Multi-path) 100% 통합 및 복원**: 병합 시 기존 카테고리의 물리 경로 목록에 신규 경로가 자동 결합되어 통합 관리.
