---
title: "설치 가이드"
project: "BookOasis"
category: "guide"
date: 2026-06-22
tags: [install, guide, setup]
---

# 📦 북 오아시스 (BookOasis) 설치 가이드

이 문서는 북 오아시스 미디어 서버를 로컬 환경 및 Linux 운영 서버에 설치하고 서비스를 구동하기 위한 통합 안내서입니다.

---

## 1. 시스템 요구사항

* **운영체제**: Windows 10/11, Linux (Ubuntu 20.04+ 권장), macOS
* **Python**: 3.9 이상 권장
* **데이터베이스**: SQLite (Python 내장 라이브러리로 별도 설치 불필요)
* **네트워크**: 외부 통신(알라딘 API 메타데이터 연동 목적) 및 리버스 프록시 환경 지원

---

## 2. 설치 단계 (Quick Start)

### ① 소스 코드 복제 및 가상환경 구성
프로젝트 코드를 준비하고 파이썬 가상환경(venv)을 생성하여 격리합니다.

**Linux / macOS:**
```bash
git clone https://github.com/your-repo/BookOasis.git
cd BookOasis
python -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/your-repo/BookOasis.git
cd BookOasis
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### ② 의존성 패키지 설치
`requirements.txt`에 명시된 핵심 종속 패키지들을 설치합니다.
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### ③ 환경 변수 설정 (선택)

과거 버전에 존재하던 `.env` 파일의 복잡한 설정(플러그인 활성화, API 키 등)은 모두 폐기되었으며, 최신 아키텍처에서는 시스템 구동 후 웹 브라우저의 **[환경설정 > 플러그인 설정]** 탭에서 안전하게 DB에 직접 저장하고 관리합니다. 따라서 특별한 목적이 없다면 별도의 환경 변수 파일 생성 없이 곧바로 실행 단계로 넘어가셔도 무방합니다.

다만, Gunicorn 워커 프로세스가 메모리 한계점 감지로 자진 재구동되거나 시스템이 재시작될 때 **웹 로그인 상태가 풀리지 않고 유지**되도록 하려면, 프로젝트 루트에 `.env` 파일을 생성하고 고정된 암호화 키(`SECRET_KEY`)를 등록해야 합니다.

**.env 파일 구성 예시:**
```env
# Gunicorn 재구동 시 사용자 로그인 세션 유지를 위한 고정 키
SECRET_KEY=yoursupersecretfixedkey12345!
```

---

## 3. 웹 서비스 실행

### 1) 로컬 개발 및 Windows 원클릭 실행 (Windows / macOS / Linux)

#### 🪟 Windows 환경
윈도우 환경에서는 번잡한 가상환경 생성이나 패키지 수동 설치 과정 없이, 마우스 더블클릭 한 번으로 구동에 필요한 모든 폴더(`db`, `covers`, `cache`, `logs`) 생성 및 라이브러리(`waitress` 포함) 설치, 프로덕션 기동까지 처리해 주는 배치 파일을 제공합니다.

1. 프로젝트 루트의 **`run_windows.bat`** 파일을 마우스 더블클릭하여 실행합니다.
2. 기동이 성공하면 자동으로 `http://localhost:5930` 웹 주소로 서빙이 시작됩니다.

#### 🐧 Linux / macOS 환경
디버그 환경 및 로컬 테스트를 위해 내장 Werkzeug 웹 서버로 실행합니다.
```bash
# 기본 실행 (포트 5930)
python core.py

# 포트를 변경하여 실행할 경우 (-p 파라미터 사용)
python core.py -p 8080
```
* 기본 구동 포트: `http://localhost:5930` (파라미터로 변경 가능)

### 2) 운영 서버 배포 모드 (Linux - Gunicorn)
Linux 서버 환경에서는 락 현상을 예방하고 멀티 워커 처리를 위해 Gunicorn을 이용하여 안정적으로 서비스를 구동합니다.

```bash
# 백그라운드 구동 예시 (기본 5930 포트 사용)
gunicorn --workers 4 --bind 0.0.0.0:5930 --timeout 120 api:app --daemon

# 만약 포트를 8080으로 변경하고 싶다면 바인딩 옵션을 수정하세요:
# gunicorn --workers 4 --bind 0.0.0.0:8080 --timeout 120 api:app --daemon
```

### 3) Docker 기반 간편 실행
도커 환경이 설치되어 있다면, 환경 구성을 빌드 없이 컨테이너 기반으로 빠르게 기동할 수 있습니다.

**① 설정 템플릿 복사**
로컬 환경 고유 설정을 위해 제공되는 오버라이드 템플릿 파일을 복사합니다.
```bash
cp docker-compose.override.example.yml docker-compose.override.yml
```

**② 볼륨 바인딩 경로 수정**
생성된 `docker-compose.override.yml` 파일을 열어 본인의 실제 책/만화책 라이브러리 디렉토리 경로로 수정합니다.
```yaml
services:
  bookoasis:
    volumes:
      - /실제/책/저장/경로:/data/comics:ro
```

**③ 서비스 실행 (GHCR 이미지 기반)**
```bash
# 최초 실행 (로컬 빌드 없이 GHCR 이미지 사용)
docker compose -f docker-compose.ghcr.yml -f docker-compose.override.yml up -d

# 업데이트 시
docker compose -f docker-compose.ghcr.yml -f docker-compose.override.yml pull
docker compose -f docker-compose.ghcr.yml -f docker-compose.override.yml up -d
```
* 기본 경로는 GHCR 이미지를 사용하므로 사용자가 직접 Docker 이미지를 빌드할 필요가 없습니다.
* 컨테이너 내부 포트 `5930`이 호스트의 `5930` 포트로 바인딩됩니다. 호스트 포트를 변경하고 싶다면 `docker-compose.ghcr.yml` 파일에서 `ports: - "8080:5930"`과 같이 좌측 포트 번호를 수정하십시오.
* 데이터베이스(`db/`), 표지 캐시(`covers/`), 임시 업로드 폴더(`cache/`), 커스텀 플러그인(`plugins/`)이 프로젝트 루트 디렉터리에 영구 보존용 볼륨으로 자동 매핑됩니다.
* 💡 `plugins/` 볼륨 매핑 덕분에 도커 컨테이너를 다시 빌드할 필요 없이 호스트의 `plugins/metadata/` 폴더에 새 파이썬 파일을 넣기만 하면 외부 메타데이터 플러그인을 즉시 추가할 수 있습니다.
* 💡 `docker-compose.override.yml`은 `.gitignore`에 등록되어 있으므로 향후 업데이트(`git pull`) 시 사용자의 개인 설정이 충돌하거나 초기화되지 않습니다.

> 보안 정책: 운영자 전용 배포/릴리스 자동화 절차는 비공개 내부 문서로 관리합니다.

---

## 4. 리버스 프록시 및 클라우드플레어(Cloudflare) 설정

서비스를 외부 도메인과 연동할 때, 앞단에 클라우드플레어(프록시 모드)를 두고 오리진 서버에서 Nginx를 리버스 프록시로 사용할 때의 최적화 설정입니다.

> [!NOTE]
> 클라우드플레어 Free 플랜의 업로드 한도인 **100MB** 규격에 최적화되어 있으며, 만화책 이미지 대량 조회 시 발생하는 병목을 막기 위해 **Nginx 버퍼링을 비활성화**합니다.

### Nginx 가상 호스트 설정 예시 (`/etc/nginx/sites-available/book`)

```nginx
server {
    listen 80;
    server_name book.yourdomain.com; # 본인의 도메인으로 변경하세요

    # HTTPS 리다이렉트 (Cloudflare 환경에서 프로토콜 감지 시)
    if ($http_x_forwarded_proto = "http") {
        return 301 https://$host$request_uri/;
    }

    # 1. Gzip 압축 설정
    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # 2. 업로드 용량 제한 및 버퍼 확장
    client_max_body_size 100M;
    
    # Cloudflare 헤더/쿠키 처리를 위해 버퍼 크기 대폭 확장 (4XX 에러 방지)
    client_header_buffer_size 16k;
    large_client_header_buffers 4 64k;
    proxy_headers_hash_max_size 1024;
    proxy_headers_hash_bucket_size 128;

    # 3. 보안 헤더 추가
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # 4. Cloudflare 실제 IP 반영 설정
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.254.85.0/24;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/25;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;

    real_ip_header CF-Connecting-IP;

    # 5. 리버스 프록시 연동 및 성능 최적화
    location / {
        proxy_pass http://127.0.0.1:5930/;

        # 기본 프록시 헤더 설정 ($host에서 $http_host로 변경하여 포트 유지 및 호환성 강화)
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;

        # WebSocket 연결 유지 (실시간 모니터링/진행도 갱신용)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 만화책 대용량 파일 전송 최적화 (중간 버퍼링 끄고 즉시 스트리밍)
        proxy_buffering off;

        # AI 분석 등 장시간 작업 처리 대응 타임아웃
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

Nginx 설정 변경 후에는 `sudo nginx -t`로 검증하고 `sudo systemctl reload nginx`를 통해 설정을 적용하십시오.

### Caddy 설정 예시 (`/etc/caddy/Caddyfile`)

Caddy를 리버스 프록시로 채택할 경우 아래와 같이 간결하게 구성할 수 있습니다. Caddy는 자체적으로 Let's Encrypt를 통한 HTTPS 인증서 자동 갱신 및 WebSocket 프록시 처리를 완벽하게 대행합니다.

```caddy
your-domain.com { # <== 본인의 도메인으로 설정하세요
    # Gzip 및 Zstd 텍스트 압축 설정
    encode gzip zstd

    # 최대 업로드 바디 제한 (Cloudflare 100MB 업로드 제한 규격 대응)
    request_body {
        max_size 100mb
    }

    # 백엔드 프록시 경로 매핑
    reverse_proxy 127.0.0.1:5930 {
        # [CRITICAL] 대용량 만화책 전송을 위한 중간 프록시 버퍼링 완전 해제
        flush_interval -1
    }
}
```

Caddyfile 편집을 마친 후 `sudo systemctl reload caddy` 명령으로 리로드하여 반영하십시오.

---

## 5. 운영 환경 보안 권장 사항 (Security Best Practices)

외부망에 서비스를 노출할 때, 잠재적인 위협(우회 침투, 로그인 무차별 대입)을 방어하기 위한 추가 보안 가이드입니다.

### ① 직접 IP 접속 차단 (오리진 서버 보호)
도메인이 아닌 서버의 공인 IP 자체를 스캔하여 들어오는 다이렉트 트래픽을 차단합니다. Nginx 설정 파일에 기본 서버(`default_server`) 블록을 추가하여 Cloudflare를 거치지 않은 우회 요청의 접속을 끊어줍니다.

```nginx
# 도메인 없이 IP로 직접 유입되는 미승인 요청 차단
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    # 응답 헤더조차 반환하지 않고 즉시 커넥션을 끊어 자원 보호
    return 444; 
}
```

### ② 로그인 엔드포인트 속도 제한 (Rate Limiting)
관리자 계정 등의 무차별 대입(Brute Force) 해킹을 차단하기 위해 로그인 경로에 요청 제한을 설정합니다.

`nginx.conf` (`http` 블록 내부):
```nginx
# IP당 초당 1회 제한 및 10MB 메모리 크기 영역 생성
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=1r/s;
```

가상 호스트 설정 파일 (`server` 블록 내부):
```nginx
location /api/auth/login {
    # 지정한 속도 제한 적용 (최대 5개까지 버스트 허용)
    limit_req zone=login_limit burst=5 nodelay;
    
    proxy_pass http://127.0.0.1:5930;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### ③ Cloudflare WAF 설정 권장
* **국가 기반 차단 (Geoblocking)**: 국내 전용 서재인 경우, Cloudflare 대시보드의 WAF 규칙(WAF Rules)을 활용하여 대한민국(`South Korea`) 이외 국가의 모든 트래픽에 `Managed Challenge(CAPTCHA)`를 강제 부여하십시오. 스캐너 봇 트래픽의 95% 이상을 차단할 수 있습니다.
* **Super Bot Fight Mode**: 스캔 도구를 차단하도록 봇 대응 옵션을 켜두는 것을 권장합니다.
