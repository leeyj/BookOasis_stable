#!/usr/bin/env bash
# ============================================================
#  BookOasis — Interactive Install Script
#  지원 환경: Linux / macOS (bash/zsh)
#  사용법: bash install.sh
# ============================================================

set -euo pipefail

# ── 색상 정의 ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── 헬퍼 함수 ────────────────────────────────────────────────
print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║        📚  BookOasis  설치 마법사            ║"
    echo "  ║   Personal Comic & Book Media Server         ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${RESET}"
}

step_header() {
    local step="$1"
    local total="$2"
    local title="$3"
    echo ""
    echo -e "${CYAN}${BOLD}━━━ STEP ${step}/${total}: ${title} ━━━${RESET}"
    echo ""
}

info()    { echo -e "  ${CYAN}ℹ ${RESET}$*"; }
success() { echo -e "  ${GREEN}✔ ${RESET}$*"; }
warn()    { echo -e "  ${YELLOW}⚠ ${RESET}$*"; }
error()   { echo -e "  ${RED}✖ ${RESET}$*"; }
prompt()  { echo -e "  ${BOLD}▶ $*${RESET}"; }

# ── 임의 키 생성 ─────────────────────────────────────────────
generate_random_key() {
    local length="${1:-48}"
    if command -v openssl &>/dev/null; then
        openssl rand -base64 $length | tr -dc 'a-zA-Z0-9!@#$%^&*' | head -c $length
    elif [ -r /dev/urandom ]; then
        tr -dc 'a-zA-Z0-9!@#$%^&*' < /dev/urandom | head -c $length
    elif command -v python3 &>/dev/null; then
        python3 -c "import secrets; print(secrets.token_urlsafe($length)[:$length])"
    else
        echo "CHANGE_ME_$(date +%s | sha256sum 2>/dev/null | head -c $length || date +%s)"
    fi
}

# ── 경로 expand ───────────────────────────────────────────────
expand_path() {
    local p="$1"
    echo "${p/#\~/$HOME}"
}

# ════════════════════════════════════════════════════════════
#  메인 실행
# ════════════════════════════════════════════════════════════
print_banner

echo -e "${DIM}  이 스크립트는 BookOasis를 단계별로 안내합니다."
echo -e "  언제든지 Ctrl+C로 중단할 수 있습니다.${RESET}"
echo ""

# ────────────────────────────────────────────────────────────
# STEP 1: 설치 방식 선택 (Docker vs Native)
# ────────────────────────────────────────────────────────────
step_header 1 4 "설치 방식 선택"

echo -e "  ${BOLD}어떤 방식으로 BookOasis를 실행하시겠습니까?${RESET}"
echo ""
echo -e "  ${GREEN}[1]${RESET} 🐳 Docker   ${DIM}(권장 — Redis 포함, 빌드 자동화, 환경 격리)${RESET}"
echo -e "  ${YELLOW}[2]${RESET} 🐍 Native  ${DIM}(Python 직접 실행 — 가볍고 리소스 절약)${RESET}"
echo ""

INSTALL_MODE=""
while true; do
    prompt "선택하세요 [1/2] (기본값: 1): "
    read -r MODE_INPUT
    MODE_INPUT="${MODE_INPUT:-1}"
    case "$MODE_INPUT" in
        1) INSTALL_MODE="docker"; break ;;
        2) INSTALL_MODE="native"; break ;;
        *) warn "1 또는 2를 입력해 주세요." ;;
    esac
done

if [ "$INSTALL_MODE" = "docker" ]; then
    success "Docker 방식을 선택했습니다."

    echo ""
    info "Docker 및 Docker Compose 설치 여부 확인 중..."
    if ! command -v docker &>/dev/null; then
        error "Docker가 설치되어 있지 않습니다."
        echo -e "  ${DIM}→ https://docs.docker.com/get-docker/ 에서 설치 후 다시 실행해 주세요.${RESET}"
        exit 1
    fi

    COMPOSE_CMD=""
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        error "Docker Compose를 찾을 수 없습니다."
        echo -e "  ${DIM}→ Docker Desktop 설치 또는 'docker compose' 플러그인을 설치해 주세요.${RESET}"
        exit 1
    fi

    success "Docker: $(docker --version)"
    success "Compose: $COMPOSE_CMD"

    echo ""
    echo -e "  ${BOLD}Docker 이미지 방식을 선택해 주세요:${RESET}"
    echo ""
    echo -e "  ${GREEN}[1]${RESET} GHCR 이미지  ${DIM}(ghcr.io — 빌드 없이 즉시 다운로드, 권장)${RESET}"
    echo -e "  ${YELLOW}[2]${RESET} 로컬 빌드    ${DIM}(소스에서 직접 빌드 — 개발/커스텀용)${RESET}"
    echo ""

    DOCKER_IMAGE_MODE=""
    while true; do
        prompt "선택하세요 [1/2] (기본값: 1): "
        read -r IMG_INPUT
        IMG_INPUT="${IMG_INPUT:-1}"
        case "$IMG_INPUT" in
            1) DOCKER_IMAGE_MODE="ghcr"; break ;;
            2) DOCKER_IMAGE_MODE="build"; break ;;
            *) warn "1 또는 2를 입력해 주세요." ;;
        esac
    done

else
    success "Native Python 방식을 선택했습니다."
    DOCKER_IMAGE_MODE="none"

    info "Python3 설치 여부 확인 중..."
    if ! command -v python3 &>/dev/null; then
        error "Python 3가 설치되어 있지 않습니다."
        echo -e "  ${DIM}→ https://www.python.org/downloads/ 에서 Python 3.10+ 를 설치해 주세요.${RESET}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version 2>&1)
    success "Python: $PYTHON_VERSION"
fi

# ────────────────────────────────────────────────────────────
# STEP 2: 설치 디렉토리 경로 입력
# ────────────────────────────────────────────────────────────
step_header 2 4 "설치 디렉토리 경로 설정"

echo -e "  BookOasis가 설치될 디렉토리를 지정합니다."
echo -e "  ${DIM}(데이터베이스, 커버 이미지, 캐시 파일이 이 경로 하위에 저장됩니다)${RESET}"
echo ""

DEFAULT_INSTALL_DIR="$HOME/bookoasis"
INSTALL_DIR=""

while true; do
    prompt "설치 경로를 입력하세요 (기본값: ${DEFAULT_INSTALL_DIR}): "
    read -r DIR_INPUT
    DIR_INPUT="${DIR_INPUT:-$DEFAULT_INSTALL_DIR}"
    INSTALL_DIR="$(expand_path "$DIR_INPUT")"

    if [ -d "$INSTALL_DIR" ]; then
        warn "해당 디렉토리가 이미 존재합니다: $INSTALL_DIR"
        prompt "기존 디렉토리를 사용하시겠습니까? [Y/n]: "
        read -r CONFIRM
        CONFIRM="${CONFIRM:-Y}"
        if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
            success "기존 디렉토리를 사용합니다: $INSTALL_DIR"
            break
        fi
    else
        success "설치 경로: $INSTALL_DIR"
        break
    fi
done

# ────────────────────────────────────────────────────────────
# STEP 3: 만화책/도서 라이브러리 경로 입력
# ────────────────────────────────────────────────────────────
step_header 3 4 "만화책 / 도서 라이브러리 경로"

echo -e "  BookOasis가 스캔할 ${BOLD}만화책 및 도서 파일이 있는 디렉토리${RESET}를 입력합니다."
echo -e "  ${DIM}(ZIP / CBZ / CBR / EPUB / PDF 등 파일이 저장된 경로)${RESET}"
echo ""

LIBRARY_DIR=""
while true; do
    prompt "도서/만화책 디렉토리 경로를 입력하세요: "
    read -r LIB_INPUT
    LIB_INPUT="$(expand_path "$LIB_INPUT")"

    if [ -z "$LIB_INPUT" ]; then
        warn "경로를 입력해 주세요."
        continue
    fi

    if [ -d "$LIB_INPUT" ]; then
        LIBRARY_DIR="$LIB_INPUT"
        success "라이브러리 경로: $LIBRARY_DIR"
        break
    else
        warn "해당 경로가 존재하지 않습니다: $LIB_INPUT"
        prompt "존재하지 않는 경로를 그대로 사용하시겠습니까? (Docker 마운트 경로인 경우 가능) [y/N]: "
        read -r FORCE_CONFIRM
        FORCE_CONFIRM="${FORCE_CONFIRM:-N}"
        if [[ "$FORCE_CONFIRM" =~ ^[Yy]$ ]]; then
            LIBRARY_DIR="$LIB_INPUT"
            warn "경로가 없지만 그대로 사용합니다: $LIBRARY_DIR"
            break
        fi
    fi
done

# ────────────────────────────────────────────────────────────
# STEP 4: 보안 키 설정 (SECRET_KEY, WEBHOOK_TOKEN)
# ────────────────────────────────────────────────────────────
step_header 4 4 "보안 키 설정"

echo -e "  ${BOLD}SECRET_KEY${RESET}  — Flask 세션 암호화 키 (고정 필수)"
echo -e "  ${DIM}  서버를 재시작해도 사용자 로그인 세션이 유지됩니다.${RESET}"
echo ""
echo -e "  ${BOLD}WEBHOOK_TOKEN${RESET} — 외부 연동 웹훅 API 보안 토큰"
echo -e "  ${DIM}  외부 서비스에서 BookOasis API 호출 시 사용합니다.${RESET}"
echo ""

AUTO_SECRET=$(generate_random_key 48)
AUTO_WEBHOOK=$(generate_random_key 32)

echo -e "  ${DIM}자동 생성된 추천 값:${RESET}"
echo -e "  ${DIM}  SECRET_KEY    = ${AUTO_SECRET}${RESET}"
echo -e "  ${DIM}  WEBHOOK_TOKEN = ${AUTO_WEBHOOK}${RESET}"
echo ""

echo -e "  ${BOLD}[SECRET_KEY]${RESET}"
prompt "직접 입력하거나 Enter를 눌러 자동 생성 값 사용: "
read -r SK_INPUT
SECRET_KEY="${SK_INPUT:-$AUTO_SECRET}"
if [ -z "$SK_INPUT" ]; then
    info "자동 생성 SECRET_KEY를 사용합니다."
else
    success "직접 입력한 SECRET_KEY를 사용합니다."
fi

echo ""
echo -e "  ${BOLD}[WEBHOOK_TOKEN]${RESET}"
prompt "직접 입력하거나 Enter를 눌러 자동 생성 값 사용: "
read -r WT_INPUT
WEBHOOK_TOKEN="${WT_INPUT:-$AUTO_WEBHOOK}"
if [ -z "$WT_INPUT" ]; then
    info "자동 생성 WEBHOOK_TOKEN을 사용합니다."
else
    success "직접 입력한 WEBHOOK_TOKEN을 사용합니다."
fi

# ════════════════════════════════════════════════════════════
#  설정 요약 및 최종 확인
# ════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}━━━ 설치 요약 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  설치 방식      : ${BOLD}${INSTALL_MODE}${RESET}"
if [ "$INSTALL_MODE" = "docker" ]; then
    if [ "$DOCKER_IMAGE_MODE" = "ghcr" ]; then
        echo -e "  Docker 이미지   : ${BOLD}GHCR (ghcr.io/leeyj/bookoasis:stable)${RESET}"
    else
        echo -e "  Docker 이미지   : ${BOLD}로컬 빌드${RESET}"
    fi
fi
echo -e "  설치 경로      : ${BOLD}${INSTALL_DIR}${RESET}"
echo -e "  라이브러리 경로 : ${BOLD}${LIBRARY_DIR}${RESET}"
echo -e "  SECRET_KEY     : ${DIM}${SECRET_KEY:0:12}... (${#SECRET_KEY}자)${RESET}"
echo -e "  WEBHOOK_TOKEN  : ${DIM}${WEBHOOK_TOKEN:0:8}... (${#WEBHOOK_TOKEN}자)${RESET}"
echo ""

prompt "위 설정으로 설치를 진행하시겠습니까? [Y/n]: "
read -r FINAL_CONFIRM
FINAL_CONFIRM="${FINAL_CONFIRM:-Y}"
if [[ ! "$FINAL_CONFIRM" =~ ^[Yy]$ ]]; then
    warn "설치가 취소되었습니다."
    exit 0
fi

# ════════════════════════════════════════════════════════════
#  실제 설치 수행
# ════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}${BOLD}━━━ 설치 시작 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# 디렉토리 생성
info "디렉토리 생성 중..."
mkdir -p "$INSTALL_DIR"/{db,covers,cache,logs}
success "디렉토리 생성 완료: $INSTALL_DIR"

# 소스 복사 (현재 디렉토리와 설치 경로가 다를 경우)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$INSTALL_DIR" != "$SCRIPT_DIR" ]; then
    info "소스 파일 복사 중: $SCRIPT_DIR → $INSTALL_DIR"
    if command -v rsync &>/dev/null; then
        rsync -a --exclude='.git' \
                  --exclude='.venv' \
                  --exclude='venv' \
                  --exclude='db' \
                  --exclude='covers' \
                  --exclude='cache' \
                  --exclude='logs' \
                  --exclude='*.pyc' \
                  --exclude='__pycache__' \
                  --exclude='.env' \
                  "$SCRIPT_DIR/" "$INSTALL_DIR/"
    else
        cp -rn "$SCRIPT_DIR/." "$INSTALL_DIR/" 2>/dev/null || true
    fi
    success "소스 복사 완료."
else
    info "소스와 설치 경로가 동일합니다. 복사를 건너뜁니다."
fi

# .env 파일 생성
info ".env 설정 파일 생성 중..."
ENV_FILE="$INSTALL_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    BACKUP_FILE="${ENV_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
    warn ".env 파일이 이미 존재합니다. 백업 후 새로 생성합니다: $BACKUP_FILE"
    cp "$ENV_FILE" "$BACKUP_FILE"
fi

cat > "$ENV_FILE" << ENVEOF
# ============================================================
#  BookOasis 환경 설정
#  생성일시: $(date '+%Y-%m-%d %H:%M:%S')
#  설치 방식: ${INSTALL_MODE}
#  install.sh 에 의해 자동 생성되었습니다.
# ============================================================

# 데이터베이스 엔진 (sqlite 기본, postgresql은 향후 지원 예정)
DBMS=sqlite

# Flask 세션 암호화 키 — 서버 재시작 시 로그인 세션 유지를 위해 반드시 고정 값 사용
SECRET_KEY=${SECRET_KEY}

# 외부 연동 웹훅 API 보안 토큰
WEBHOOK_TOKEN=${WEBHOOK_TOKEN}

# 콘솔 뷰어 로깅 제어 (디버그 시에만 true로 변경)
VIEW_LOG=false

# SCAN JSONL 초기화 여부
SCAN_JSONL_REMOVE=false
ENVEOF

success ".env 파일 생성 완료."

# ──────────────────────────────────────────────────────────────
# Docker 모드 처리
# ──────────────────────────────────────────────────────────────
if [ "$INSTALL_MODE" = "docker" ]; then

    # Redis URL 추가 (Docker는 컨테이너 내부 네트워크로 자동 연동)
    cat >> "$ENV_FILE" << ENVEOF2

# Docker 환경 Redis 자동 연동 (컨테이너 내부 네트워크, 수정 불필요)
REDIS_URL=redis://redis:6379/0
ENVEOF2

    # docker-compose.override.yml 생성
    info "docker-compose.override.yml 생성 중..."
    OVERRIDE_FILE="$INSTALL_DIR/docker-compose.override.yml"

    cat > "$OVERRIDE_FILE" << OVERRIDEEOF
# ============================================================
#  BookOasis Docker Compose Override
#  생성일시: $(date '+%Y-%m-%d %H:%M:%S')
#  install.sh 에 의해 자동 생성된 파일입니다.
#  이 파일은 .gitignore에 포함되므로 git pull 후에도 유지됩니다.
# ============================================================
version: "3.8"

services:
  bookoasis:
    volumes:
      # 📚 도서/만화책 라이브러리 경로 (읽기 전용 마운트)
      - ${LIBRARY_DIR}:/data/comics:ro
OVERRIDEEOF

    success "docker-compose.override.yml 생성 완료."

    # 컨테이너 실행
    echo ""
    info "Docker 컨테이너를 시작합니다..."
    cd "$INSTALL_DIR"

    if [ "$DOCKER_IMAGE_MODE" = "ghcr" ]; then
        info "GHCR 이미지 풀링 중... (인터넷 연결 필요, 수 분 소요)"
        $COMPOSE_CMD -f docker-compose.ghcr.yml -f docker-compose.override.yml up -d
    else
        info "로컬 이미지 빌드 중... (수 분이 소요될 수 있습니다)"
        $COMPOSE_CMD up -d --build
    fi

    echo ""
    success "🎉 BookOasis Docker 실행 완료!"
    echo ""
    echo -e "  ${CYAN}${BOLD}━━━ 실행 정보 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "  🌐 접속 URL      : ${BOLD}http://localhost:5930${RESET}"
    echo -e "  👤 초기 계정     : ${BOLD}admin / admin${RESET}"
    echo -e "  📁 설치 경로     : ${BOLD}${INSTALL_DIR}${RESET}"
    echo -e "  📚 라이브러리    : ${BOLD}${LIBRARY_DIR}${RESET}"
    echo ""
    echo -e "  ${DIM}컨테이너 로그 확인 : ${COMPOSE_CMD} logs -f bookoasis${RESET}"
    echo -e "  ${DIM}컨테이너 중지      : ${COMPOSE_CMD} down${RESET}"
    echo -e "  ${DIM}컨테이너 업데이트  : ${COMPOSE_CMD} pull && ${COMPOSE_CMD} up -d${RESET}"

# ──────────────────────────────────────────────────────────────
# Native 모드 처리
# ──────────────────────────────────────────────────────────────
else

    # BOOKS_DIR 환경변수 추가
    cat >> "$ENV_FILE" << ENVEOF3

# 도서/만화책 라이브러리 경로 (Native 모드)
BOOKS_DIR=${LIBRARY_DIR}

# [옵션] Redis 캐시 연동 — 설치 후 Redis 구동 시 아래 주석 해제
# REDIS_URL=redis://127.0.0.1:6379/9
ENVEOF3

    # 가상환경 생성
    info "Python 가상환경 생성 중..."
    VENV_DIR="$INSTALL_DIR/venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        success "가상환경 생성 완료: $VENV_DIR"
    else
        info "기존 가상환경을 재사용합니다: $VENV_DIR"
    fi

    # 패키지 설치
    info "Python 패키지 설치 중... (수 분이 소요될 수 있습니다)"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    success "패키지 설치 완료."

    # ── Linux systemd 서비스 등록 (선택) ──────────────────────
    if command -v systemctl &>/dev/null && [ "$(uname)" = "Linux" ]; then
        echo ""
        echo -e "  ${BOLD}[선택] systemd 서비스 등록${RESET}"
        echo -e "  ${DIM}  등록 시 서버 부팅 시 자동으로 BookOasis가 시작됩니다.${RESET}"
        prompt "systemd 서비스로 등록하시겠습니까? [Y/n]: "
        read -r SYSTEMD_CONFIRM
        SYSTEMD_CONFIRM="${SYSTEMD_CONFIRM:-Y}"

        if [[ "$SYSTEMD_CONFIRM" =~ ^[Yy]$ ]]; then
            CURRENT_USER=$(whoami)
            SERVICE_FILE="/etc/systemd/system/bookoasis.service"
            info "systemd 서비스 파일 생성 중... (sudo 권한 필요)"

            sudo tee "$SERVICE_FILE" > /dev/null << SVCEOF
[Unit]
Description=BookOasis - Personal Book & Comic Media Server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/core.py
Restart=on-failure
RestartSec=5
EnvironmentFile=${INSTALL_DIR}/.env

[Install]
WantedBy=multi-user.target
SVCEOF

            sudo systemctl daemon-reload
            sudo systemctl enable bookoasis
            sudo systemctl start bookoasis
            success "systemd 서비스 등록 및 시작 완료."
            info "상태 확인: sudo systemctl status bookoasis"
        fi
    fi

    # ── macOS launchd 서비스 등록 (선택) ──────────────────────
    if [[ "$(uname)" == "Darwin" ]]; then
        echo ""
        echo -e "  ${BOLD}[선택] launchd 서비스 등록 (macOS)${RESET}"
        echo -e "  ${DIM}  등록 시 로그인 시 자동으로 BookOasis가 시작됩니다.${RESET}"
        prompt "launchd 서비스로 등록하시겠습니까? [Y/n]: "
        read -r LAUNCHD_CONFIRM
        LAUNCHD_CONFIRM="${LAUNCHD_CONFIRM:-Y}"

        if [[ "$LAUNCHD_CONFIRM" =~ ^[Yy]$ ]]; then
            PLIST_DIR="$HOME/Library/LaunchAgents"
            mkdir -p "$PLIST_DIR"
            PLIST_FILE="$PLIST_DIR/com.bookoasis.plist"

            cat > "$PLIST_FILE" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bookoasis</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python</string>
        <string>${INSTALL_DIR}/core.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/logs/bookoasis.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/logs/bookoasis.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SECRET_KEY</key>
        <string>${SECRET_KEY}</string>
        <key>WEBHOOK_TOKEN</key>
        <string>${WEBHOOK_TOKEN}</string>
        <key>BOOKS_DIR</key>
        <string>${LIBRARY_DIR}</string>
    </dict>
</dict>
</plist>
PLISTEOF

            launchctl load "$PLIST_FILE"
            success "launchd 서비스 등록 완료."
            info "상태 확인: launchctl list | grep bookoasis"
        fi
    fi

    echo ""
    success "🎉 BookOasis Native 설치 완료!"
    echo ""
    echo -e "  ${CYAN}${BOLD}━━━ 실행 정보 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "  🌐 접속 URL      : ${BOLD}http://localhost:5930${RESET}"
    echo -e "  👤 초기 계정     : ${BOLD}admin / admin${RESET}"
    echo -e "  📁 설치 경로     : ${BOLD}${INSTALL_DIR}${RESET}"
    echo -e "  📚 라이브러리    : ${BOLD}${LIBRARY_DIR}${RESET}"
    echo ""
    echo -e "  ${DIM}수동 실행 방법:${RESET}"
    echo -e "  ${DIM}  cd ${INSTALL_DIR}${RESET}"
    echo -e "  ${DIM}  source venv/bin/activate${RESET}"
    echo -e "  ${DIM}  python core.py${RESET}"
fi

# ════════════════════════════════════════════════════════════
#  완료 배너
# ════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   🎉  BookOasis 설치가 완료되었습니다!       ║"
echo "  ║   최초 로그인: admin / admin                 ║"
echo "  ║   (첫 로그인 후 즉시 비밀번호를 변경하세요)  ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "  ${DIM}설정 파일 위치: ${ENV_FILE}${RESET}"
echo ""
