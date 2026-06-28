# BookOasis (북 오아시스)

<p align="center">
  <img src="https://img.shields.io/badge/No_Build_Step-000000?style=for-the-badge&logo=esbuild&logoColor=white" alt="No Build" />
  <img src="https://img.shields.io/badge/Vanilla_JS-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="Vanilla JS" />
  <img src="https://img.shields.io/badge/No_Framework-FF4B4B?style=for-the-badge" alt="No Framework" />
  <img src="https://img.shields.io/badge/Native_Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Native Python" />
  <img src="https://img.shields.io/badge/Zero_Dependencies-4CAF50?style=for-the-badge" alt="Zero Dependencies" />
  <img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge" alt="AGPLv3" />
</p>

[English Version (README_EN.md)](./README_EN.md)

북 오아시스는 ZIP/CBZ 압축 파일 형태의 도서 및 만화책을 웹 환경에서 지연 없이 감상할 수 있도록 설계된 초경량, 고성능 개인 미디어 서버입니다.

서드파티 종속성을 극도로 최소화하고 파이썬 표준 라이브러리의 잠재력을 활용하여 가볍고 빠른 구동 환경을 제공합니다.

---

## 주요 특징

* 파일 무해제 실시간 스트리밍
  - 대용량 압축 파일(ZIP/CBZ)을 서버 디렉터리에 미리 압축 해제하지 않습니다. 
  - 내장 zipfile 모듈을 제어하여 필요한 페이지의 물리적 바이트 시작 오프셋만 읽어 스트리밍 전송하므로 디스크 I/O와 CPU 소모를 혁신적으로 절감합니다.

* 미니멀한 종속성
  - Flask 프레임워크 외에 무거운 ORM이나 서드파티 모듈을 배제했습니다.
  - 내장 SQLite 모듈에 고성능 커넥션 풀링과 정밀 쿼리를 입혀 성능 저하 없는 초경량 아키텍처를 실현했습니다.

* 최적화된 프론트엔드 파이프라인
  - 뷰포트 내 카드만 로드하는 지연 로딩(Lazy Loading) 및 다음 페이지 프리로딩(Preloading)을 지원하여 끊김 없는 독서 경험을 보장합니다.

* 유연한 메타데이터 플러그인
  - 플러그인 아키텍처를 내장하여 국내 환경에 특화된 알라딘 Open API 등의 외부 정보 수급 채널을 플러그인 형태로 제어합니다.
  - 책 소개글, 작가 정보, 고화질 커버를 원클릭으로 통합 반영하며 수동 메타데이터 편집기 및 표지 교체를 지원합니다.

* 모바일 뷰어 호환
  - 외부 뷰어 애플리케이션 연동을 위한 OPDS 규격을 지원하며, 데이터베이스 인증정보 기반의 Basic Authentication 보안 처리를 적용했습니다.

### 대시보드 화면

![BookOasis Dashboard](./docs/screenshot.png)

---

## 시작하기

상세한 환경 구성 및 설치 방법은 기술 문서를 참조하십시오.

* 설치 안내: [설치 가이드 (docs/guide_installation.md)](./docs/guide_installation.md)
* 관리 및 관리자 설정: [관리자 가이드 (docs/guide_admin.md)](./docs/guide_admin.md)
* 위키 포털: [기술 위키 홈 (docs/index.md)](./docs/index.md)

### 간편 구동 (Docker)

```bash
# docker-compose.yml 내 볼륨 경로 수정 후 실행
docker compose up -d --build
```

### 직접 구동 (Native Python)

```bash
# 가상환경 활성화 및 종속성 설치
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 설정 파일 구성
cp .env.example .env
# .env 파일 내 알라딘 TTBKey 등 필수 설정 입력

# 서버 기동
python api.py
```
* 로컬 포트: `http://localhost:5930`

---

## 🛡️ 프록시 헤더 인증 (Proxy Header Auth / SSO) 가이드

해외 홈랩 유저 및 OIDC 연동을 위해 **Proxy Header Auth (리버스 프록시 자동 로그인)** 기능을 지원합니다.
Authelia, Authentik 등 앞단의 리버스 프록시 인증 서버가 검증을 마치고 전달하는 HTTP 헤더(`Remote-User` 또는 `X-Forwarded-User`) 값을 신뢰하여 자동으로 BookOasis에 로그인(SSO)시킬 수 있습니다.

> [!CAUTION]
> **심각한 보안 경고**
> 이 기능은 반드시 Nginx, Authelia 등 **리버스 프록시가 헤더를 변조 및 보호하는 폐쇄망 환경**에서만 활성화해야 합니다!
> 프록시 없이 인터넷에 개방된 상태에서 이 옵션을 켤 경우, 악의적인 사용자가 헤더 조작(예: `Remote-User: admin`)만으로 관리자 권한을 탈취할 수 있는 심각한 취약점이 됩니다. 위험성을 충분히 인지한 분만 사용하세요.

**설정 방법:**
1. 어드민 계정으로 로그인 후 **일반 설정** 메뉴에 진입합니다.
2. 스크롤을 내려 **Proxy Header Auth (리버스 프록시 자동 로그인)** 항목을 찾아 토글합니다.
3. 설정을 저장한 뒤, 앞단의 Nginx/프록시 서버가 올바른 사용자명 헤더를 BookOasis 로 넘겨주도록 구성하십시오.

---

## Nginx 설정 가이드

1. 전역 설정 (nginx.conf) 업데이트
Cloudflare를 통하는 요청은 일반적인 요청보다 헤더 크기(쿠키, 인증 토큰, 프록시 헤더 등)가 훨씬 비대합니다. Nginx의 기본 헤더 버퍼 크기가 작으면 서버가 요청을 거부하고 400 Bad Request 또는 414 Request-URI Too Large 에러를 반환합니다.

이를 방지하기 위해 /etc/nginx/nginx.conf 파일의 http { ... } 블록 내부에 아래 설정을 반드시 추가하거나 확장해 주세요.
```
http {
    # ------------------------------------------------------------------
    # [Cloudflare 및 대용량 헤더 대응] 버퍼 크기 대폭 확장
    # 쿠키 및 인증 헤더가 길어질 때 발생하는 4XX 에러를 원천 차단합니다.
    # ------------------------------------------------------------------
    client_header_buffer_size 16k;
    large_client_header_buffers 4 64k;

    # ------------------------------------------------------------------
    # 프록시 헤더 해시 크기 최적화
    # 다수의 복잡한 X-Forwarded-* 헤더가 유입되어도 해시 테이블 오버플로우가 나지 않도록 합니다.
    # ------------------------------------------------------------------
    proxy_headers_hash_max_size 1024;
    proxy_headers_hash_bucket_size 128;

    # (기존의 다른 설정들...)
}
```

2. BookOasis 가상 호스트 설정 (sites-available)
/etc/nginx/sites-available/default 파일(또는 가상 호스트 설정 블록)에 아래 내용을 작성하고, sites-enabled에 심볼릭 링크를 걸어 적용합니다.

```
server {
    listen 80;
    server_name your-domain.com; # <== 본인의 도메인으로 변경하세요.

    # HTTP로 들어오는 요청을 HTTPS로 강제 리다이렉트 (보안)
    if ($http_x_forwarded_proto = "http") {
        return 301 https://$host$request_uri;
    }

    # ------------------------------------------------------------------
    # Gzip 텍스트 압축 설정 (UI 및 JSON API 가속)
    # 이미지 바이너리는 압축하지 않고, 텍스트 자원만 압축하여 CPU 자원을 아낍니다.
    # ------------------------------------------------------------------
    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # 알라딘 메타데이터 플러그인 등 커버 이미지 업로드를 고려한 최대 바디 크기 제한
    client_max_body_size 100M;

    # ------------------------------------------------------------------
    # 보안 헤더 주입
    # ------------------------------------------------------------------
    add_header X-Frame-Options "SAMEORIGIN" always;         # 클릭재킹 방지
    add_header X-Content-Type-Options "nosniff" always;     # MIME 스니핑 방지
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # ------------------------------------------------------------------
    # 메인 어플리케이션 프록시 라우팅
    # ------------------------------------------------------------------
    location / {
        proxy_pass http://127.0.0.1:5930/; # BookOasis 내부 구동 포트

        # [기본 프록시 헤더 설정]
        # $host 대신 $http_host를 사용하여 외부 포트 및 Cloudflare 호환성을 완벽히 유지합니다.
        proxy_set_header Host $http_host; 
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;

        # [WebSocket 및 HTTP/1.1 프로토콜 업그레이드 지원]
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # --------------------------------------------------------------
        # [CRITICAL] 대용량 파일 전송 최적화 (프록시 버퍼링 끔)
        # BookOasis의 핵심 기능인 '오프셋 기반 실시간 스트리밍'이 Nginx 임시 
        # 버퍼에 가로막히지 않고 브라우저 뷰어에 지연 없이 다이렉트로
        # 전달되도록 합니다. 디스크 I/O와 메모리 낭비를 방어하는 핵심 설정입니다.
        # --------------------------------------------------------------
        proxy_buffering off;

        # [타임아웃 확장] 대용량 스캔 프로세스 및 외부 AI 분석 장시간 작업 대응
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```





## 라이선스

본 프로젝트는 [GNU AGPLv3 (Affero General Public License v3.0)](./LICENSE) 규격을 따릅니다.
누구나 소스 코드를 열람, 수정, 배포할 수 있으며, 이 소프트웨어를 기반으로 한 서비스(네트워크를 통한 서비스 포함)를 제공할 경우 반드시 수정된 소스 코드를 동일한 AGPLv3 라이선스로 공개해야 합니다. 자세한 약관은 LICENSE 파일을 참조하십시오.


