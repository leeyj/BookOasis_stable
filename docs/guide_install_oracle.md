[English](guide_install_oracle_en.md)

# 오라클 클라우드 무료 서버에 설치하기 (Ubuntu, ARM/AMD)

오라클 클라우드 "Always Free" 서버에 BookOasis를 설치합니다. 서버를 처음 만져 보는 분 기준으로 썼습니다. (30분 정도)

> **검증 범위** (2026-11-03): 설치기(`get.sh`) 실행부터 접속까지, 오라클 Ubuntu 이미지의 기본 방화벽 규칙과 Docker의 관계, arm64 이미지 실행을 Ubuntu에서 그대로 재현해 확인했습니다.
> 오라클 콘솔 화면(인스턴스 만들기, 보안 목록)은 직접 확인하지 못했습니다. 화면이 다르면 커뮤니티에 알려 주세요.

---

## 0. 서버(인스턴스) 만들기 팁

- 이미지: **Ubuntu** (22.04 또는 24.04)
- 모양(Shape)
  - **ARM (Ampere A1)**: 무료 한도가 커서(최대 4코어/24GB) 가장 좋지만, 인기 지역은 "Out of capacity"로 몇 달씩 안 만들어지기도 합니다.
    - 사양을 **1 OCPU / 6GB**로 줄여 신청하면 잘 만들어지는 편입니다. 나중에 늘릴 수 있습니다.
    - 계정을 **종량제(Pay As You Go)** 로 바꾸면 무료 한도 안에서는 여전히 무료이고, 생성이 훨씬 잘 된다는 후기가 많습니다. 실수로 유료 자원을 만들 수 있으니 **예산 알림(Budget)을 꼭 설정**하세요.
  - **AMD (E2.1.Micro)**: 쉽게 만들어지지만 메모리가 1GB라 BookOasis를 오래 돌리기엔 빠듯합니다. 설치 연습용으로는 충분합니다.
- 공인 IP를 받고, SSH 키를 내려받아 둡니다.

BookOasis 공식 이미지는 **ARM(arm64)과 AMD(amd64)를 둘 다** 제공합니다. 같은 명령으로 설치하면 서버에 맞는 것이 자동으로 받아집니다.
(arm64 이미지를 직접 띄워 정상 기동까지 확인했습니다. 단, 그래픽카드 하드웨어 변환(VAAPI)은 amd64 전용입니다.)

---

## 1. 접속 포트 열기 — 오라클 콘솔 "보안 목록"

오라클은 서버 바깥에 방화벽이 한 겹 더 있습니다. 여기서 열지 않으면 아무리 해도 접속되지 않습니다.

**네트워킹 → 가상 클라우드 네트워크 → (내 VCN) → 서브넷 → 보안 목록 → 수신 규칙 추가**

| 항목 | 값 |
|---|---|
| 소스 CIDR | `0.0.0.0/0` (모든 곳) — 아래 "보안"을 꼭 읽어 주세요 |
| IP 프로토콜 | TCP |
| 대상 포트 범위 | `5930` |

---

## 2. 서버에 접속해 Docker 설치

내 PC에서 (Windows는 PowerShell):

```bash
ssh -i 내키파일.key ubuntu@서버공인IP
```

서버에서:

```bash
sudo apt update && sudo apt install -y git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

`exit`로 나갔다가 **다시 접속**해야 `docker` 명령을 `sudo` 없이 쓸 수 있습니다. 확인:

```bash
docker compose version
```

`Docker Compose version v2…`가 나오면 성공입니다.

> 서버 안의 방화벽(iptables)은 **건드리지 마세요.** 이유는 아래 5장.

---

## 3. BookOasis 설치 (설치 마법사)

책을 둘 폴더를 먼저 만듭니다. (구글 드라이브를 쓸 거라면 이 단계 대신 [구글 드라이브 연결하기](guide_rclone_gdrive.md)를 먼저 하고, 그 마운트 폴더를 쓰세요)

```bash
mkdir -p ~/books
curl -fsSL https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/get.sh | bash
```

질문에는 이렇게 답합니다.

| 질문 | 답 |
|---|---|
| 설치 방식 | `1` (Docker) |
| 이미지 방식 | `1` (GHCR, 빌드 없이 받기) |
| 설치 경로 | Enter (`~/bookoasis`) |
| 도서/만화책 디렉토리 | `/home/ubuntu/books` (위에서 만든 폴더) |
| SECRET_KEY / WEBHOOK_TOKEN | Enter, Enter (자동 생성) |
| 진행? | `Y` |

`🎉 BookOasis 설치가 완료되었습니다!`가 나오면 성공입니다. 서버에서 확인:

```bash
curl -s http://localhost:5930/health
```

`{"service":"BookOasis","status":"healthy"}`

---

## 4. 접속하고 첫 카테고리 만들기

브라우저에서 `http://서버공인IP:5930`

- 처음 계정 `admin` / `admin` → **비밀번호 변경 화면이 먼저 나옵니다** (바꾸기 전에는 다른 기능을 쓸 수 없음)
- **카테고리 추가** → 경로에 **`/data/comics`** → 저장

> ⚠️ 경로는 서버 폴더(`/home/ubuntu/books`)가 **아니라 `/data/comics`** 입니다. 설치 마법사가 내 책 폴더를 BookOasis 안에서 `/data/comics`라는 이름으로 연결해 두었기 때문입니다.
> 서버 경로를 적으면 "다음 경로들이 서버에 존재하지 않거나 오타가 있습니다" 오류가 납니다. (직접 재현함)

---

## 5. 방화벽 이야기 (중요)

인터넷의 오라클 안내에는 "iptables에서 포트를 열고 `netfilter-persistent save`" 하라는 글이 많습니다. **Docker로 설치했다면 하지 마세요.**

오라클 Ubuntu 이미지의 기본 방화벽 규칙을 그대로 재현해 확인한 결과입니다.

| 경우 | 결과 |
|---|---|
| Docker 설치, 기본 규칙 그대로 | **접속 됨** — Docker가 자기 규칙을 기본 차단 규칙보다 앞에 넣음 |
| 기본 규칙 파일을 다시 읽음 (`netfilter-persistent reload` 등) | **접속 끊김** — Docker 규칙이 지워짐 |
| Docker 없이 직접 설치(네이티브), 기본 규칙 그대로 | 접속 안 됨 |
| 네이티브 + iptables에 포트 추가 | 접속 됨 |

- **Docker 설치**: 1장의 오라클 콘솔 보안 목록만 열면 됩니다. 서버 안 iptables는 그대로 두세요.
  실수로 규칙을 다시 읽어 끊겼다면: `sudo systemctl restart docker`
- **네이티브 설치**일 때만:
  ```bash
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5930 -j ACCEPT
  sudo netfilter-persistent save
  ```

---

## 6. 보안 (공인 IP 서버라면 꼭)

오라클 서버는 인터넷에 그대로 노출됩니다.

1. **admin 비밀번호** — 4장에서 바꿨는지 다시 확인. 쉬운 비밀번호는 금방 뚫립니다.
2. **HTTPS** — `http://`는 비밀번호가 암호화되지 않고 오갑니다. 도메인이 있다면 Caddy로 간단히 HTTPS를 붙일 수 있습니다 → [설치 가이드 4장 Caddy 예시](guide_installation.md)
3. **더 안전하게: Tailscale** — 내 기기끼리만 접속되는 사설망입니다. 서버와 내 폰/PC에 Tailscale을 깔고 `http://서버의Tailscale주소:5930`으로 접속하면, 1장의 보안 목록에서 5930을 열 필요조차 없습니다.

---

## 7. 업데이트

```bash
cd ~/bookoasis
docker compose pull && docker compose up -d
```

---

## 자주 막히는 곳

| 증상 | 원인 → 해결 |
|---|---|
| 브라우저에서 접속이 안 됨(시간 초과) | 1장 오라클 콘솔 보안 목록에 5930 수신 규칙이 없음 |
| 잘 되다가 갑자기 접속이 안 됨 | iptables 규칙을 다시 읽음 → `sudo systemctl restart docker` |
| `permission denied … docker.sock` | `usermod` 후 다시 접속하지 않음 → `exit` 후 재접속 |
| 카테고리 추가 때 "존재하지 않거나 오타" | 서버 경로를 적음 → `/data/comics` |
| 설치 마법사가 "TTY를 찾을 수 없습니다" | `curl … | bash`를 스크립트·cron 안에서 실행함 → SSH 터미널에서 직접 실행 |
| 서버 디스크가 모자람 | 무료 디스크는 작음 → 책은 [구글 드라이브 연결](guide_rclone_gdrive.md)로 |

---

관련 문서: [구글 드라이브 연결 (rclone)](guide_rclone_gdrive.md) · [Synology NAS 설치](guide_install_synology.md) · [설치 가이드](guide_installation.md)
