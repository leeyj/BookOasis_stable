---
title: "CLI 카테고리 내보내기/가져오기 도구 가이드 (네이티브 & 도커 완벽 대응)"
category: "guide"
date: 2026-07-23
tags: [cli, export, import, migration, backup, multi-path, batch, zip_stored, docker, inspect]
---

# 📦 카테고리 내보내기/가져오기 CLI 도구 가이드 (`export_category.py` / `import_category.py`)

이 도구는 외부 메타데이터 검색(알라딘/네이버 등) 및 뷰어 스트리밍 offset 재계산 없이, 카테고리의 모든 DB 메타데이터와 커버 이미지를 타 시스템/백업본으로 초고속 이관할 수 있는 독립 CLI 전용 유틸리티입니다.  
**네이티브 환경은 물론 도커(Docker / Docker-Compose) 환경도 완벽 대응합니다.**

---

## 🔍 0. 가져오기 전 패키지 미리보기 검사 (`--info` / `--inspect`)

백업 패키지(`.oasis.zip`)에 **원본 디렉터리가 몇 개 들어있는지, 어떤 디렉터리 경로 구조로 구성되어 있는지 가져오기 전에 미리 확인**할 수 있습니다.

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
👉 Import Recommendation:
   Please provide 2 target path(s) (-p) when importing this package!
==========================================================
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

### **나) 카테고리 가져오기 (`import_category.py`)**
```bash
# 단일 경로 가져오기
python tools/import_category.py -i /backups/manga_21.oasis.zip -p "/volume1/mnt/GDDRIVE/READING/만화/완결A"

# N개 다중 경로 카테고리 가져오기 (-p 옵션 5개, 8개 등 개수 제한 없음)
python tools/import_category.py \
  --input /backups/novel_export.oasis.zip \
  --target-path "/volume1/mnt/GDRIVE/READING/책/YES24 북클럽/소설" \
  --target-path "/volume1/mnt/GDRIVE/READING/책/리디셀렉트/가정.생활" \
  --name "가정_살림(GDS)"
```

---

## 🐳 2. 도커 (Docker / Docker Compose) 환경 사용 가이드

호스트 OS에 파이썬이 설치되어 있지 않아도, `docker exec` 명령어를 통해 실행 중인 BookOasis 컨테이너 내부 파이썬 환경에서 즉시 실행 가능합니다.

> [!TIP]
> **💡 도커 사용자 헷갈림 방지 핵심 공식**:
> `[웹 UI의 카테고리 관리에서 입력하는 경로]  <─── 100% 동일 ───>  [-p 옵션 경로]`
> 
> **예시**: 웹 UI 카테고리 생성 시 입력한 서버 물리 경로가 `"/volume1/mnt/GDDRIVE/READING/만화/완결A"` 라면, 가져오기 명령 실행 시에도 `-p` 옵션에 똑같이 `"/volume1/mnt/GDDRIVE/READING/만화/완결A"` 를 지정하시면 됩니다!

### **가) 도커 환경 내보내기 (Export)**
호스트와 공유되는 볼륨 디렉터리(예: `/app/covers`)로 출력 경로를 지정하면 호스트 OS에 백업 패키지가 생성됩니다.

```bash
# 1) Docker 사용 시 (컨테이너 이름: bookoasis 가정)
docker exec -it bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip

# 2) Docker Compose 사용 시
docker-compose exec bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip
```

### **나) 도커 환경 가져오기 (Import)**
`-p` 지정 시 BookOasis 웹 UI에서 입력했던 서버 물리 경로를 사용합니다. N개의 다중 물리 경로인 경우 **5개든 8개든 개수 제한 없이 `-p` 옵션을 지정하려는 경로 개수만큼 반복 지정**할 수 있습니다.

#### **1) 단일 물리 경로 가져오기 예시**
```bash
# Docker 사용 시
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/manga_21.oasis.zip \
  -p "/volume1/mnt/GDDRIVE/READING/만화/완결A" \
  -n "이관된 만화 보관함"

# Docker Compose 사용 시
docker-compose exec bookoasis python tools/import_category.py \
  -i /app/covers/manga_21.oasis.zip \
  -p "/volume1/mnt/GDDRIVE/READING/만화/완결A" \
  -n "이관된 만화 보관함"
```

#### **2) N개 다중 물리 경로 가져오기 예시 (-p 옵션 N회 반복 지정, 개수 제한 없음)**
```bash
# Docker 사용 시 (2개, 5개, 8개 등 제한 없음)
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  -p "/volume1/mnt/GDRIVE/READING/책/YES24 북클럽/소설" \
  -p "/volume1/mnt/GDRIVE/READING/책/리디셀렉트/가정.생활" \
  -n "가정_살림(GDS)"

# Docker Compose 사용 시
docker-compose exec bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  -p "/volume1/mnt/GDRIVE/READING/책/YES24 북클럽/소설" \
  -p "/volume1/mnt/GDRIVE/READING/책/리디셀렉트/가정.생활" \
  -n "가정_살림(GDS)"
```

---

## 🔒 핵심 기능 정리
1. **패키지 미리보기 검사 (`--info`)**: DB 복원 전 원본 경로 구조, 개수, 권수 사전에 리포트로 확인.
2. **Docker / Docker-Compose 지원**: `docker exec` 명령어 지원으로 다양한 인프라 환경에서 간편 작동.
3. **초고속 `ZIP_STORED` 패키징**: 이미지 재압축을 생략하여 CPU 점유 0%, 수초 내 패키징 완수.
4. **파일명 중복 완벽 방지**: `{카테고리명}_{db_type}_lib{ID}_{YYYYMMDD_HHMMSS}.oasis.zip` 자동 생성.
5. **다중 물리 경로(Multi-path) 100% 1:1 복원**: 한 카테고리에 N개의 물리 경로(5개, 8개 등)가 있어도 각 경로 순번(`root_index`)에 맞게 새 수신 경로로 1:1 완벽 연결.
