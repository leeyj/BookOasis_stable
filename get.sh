#!/usr/bin/env bash
# ============================================================
#  BookOasis — Remote Bootstrap Installer
#  지원 환경: Linux / macOS (bash/zsh)
#  사용법:
#    curl -fsSL https://raw.githubusercontent.com/leeyj/BookOasis/main/get.sh | bash
#
#  이 스크립트는 install.sh 를 대체하지 않습니다.
#  소스를 내려받아 기존 install.sh(대화형 설치 마법사)에게 실행을
#  넘겨주는 "부트스트랩" 역할만 담당합니다.
#
#  주의: `curl | bash` 로 실행하면 표준입력(stdin)이 이미 스크립트
#  본문을 전달하는 파이프로 사용 중이라, install.sh 의 대화형 프롬프트
#  (read)가 즉시 EOF를 만나 아무 안내 없이 조용히 중단됩니다.
#  이를 피하기 위해 이 스크립트는 소스를 내려받은 뒤 install.sh를
#  /dev/tty(실제 터미널)에 다시 연결하여 실행합니다.
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

info()    { echo -e "  ${CYAN}ℹ ${RESET}$*"; }
success() { echo -e "  ${GREEN}✔ ${RESET}$*"; }
warn()    { echo -e "  ${YELLOW}⚠ ${RESET}$*"; }
error()   { echo -e "  ${RED}✖ ${RESET}$*"; }

# ── 설정 (환경변수로 재정의 가능) ───────────────────────────────
REPO_URL="${BOOKOASIS_REPO_URL:-https://github.com/leeyj/BookOasis_stable.git}"
REPO_BRANCH="${BOOKOASIS_REPO_BRANCH:-main}"
SRC_DIR="${BOOKOASIS_SRC_DIR:-$HOME/.bookoasis/src}"

echo ""
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║      📚  BookOasis 원격 설치 부트스트랩       ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 필수 도구 확인 ───────────────────────────────────────────
if ! command -v git &>/dev/null; then
    error "git이 설치되어 있지 않습니다. 먼저 git을 설치한 뒤 다시 실행해 주세요."
    echo -e "  ${DIM}→ Ubuntu/Debian: sudo apt install git${RESET}"
    echo -e "  ${DIM}→ macOS: brew install git${RESET}"
    exit 1
fi

# ── TTY 확인 (대화형 설치 마법사 실행에 필수) ────────────────────
if [ ! -r /dev/tty ]; then
    error "인터랙티브 입력을 받을 터미널(TTY)을 찾을 수 없습니다."
    echo -e "  ${DIM}이 스크립트는 설치 경로/라이브러리 경로 등을 직접 물어보는 대화형${RESET}"
    echo -e "  ${DIM}설치 마법사(install.sh)를 실행합니다. CI, cron, 논-인터랙티브 셸에서는${RESET}"
    echo -e "  ${DIM}사용할 수 없으니 아래처럼 저장소를 직접 클론한 뒤 install.sh를 실행해 주세요:${RESET}"
    echo ""
    echo -e "  ${DIM}  git clone ${REPO_URL} && cd BookOasis_stable && bash install.sh${RESET}"
    exit 1
fi

# ── 소스 코드 확보 (최초 clone 또는 기존 clone 업데이트) ──────────
if [ -d "$SRC_DIR/.git" ]; then
    info "기존 소스를 최신 버전으로 갱신 중: $SRC_DIR"
    git -C "$SRC_DIR" fetch --depth 1 origin "$REPO_BRANCH"
    git -C "$SRC_DIR" checkout "$REPO_BRANCH"
    git -C "$SRC_DIR" reset --hard "origin/$REPO_BRANCH"
else
    info "소스 코드를 내려받는 중: $REPO_URL → $SRC_DIR"
    mkdir -p "$(dirname "$SRC_DIR")"
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR"
fi
success "소스 준비 완료: $SRC_DIR"

if [ ! -f "$SRC_DIR/install.sh" ]; then
    error "install.sh를 찾을 수 없습니다: $SRC_DIR/install.sh"
    exit 1
fi

# ── 대화형 설치 마법사로 인계 (stdin을 실제 터미널로 재연결) ───────
echo ""
info "대화형 설치 마법사(install.sh)를 시작합니다..."
echo ""
exec bash "$SRC_DIR/install.sh" < /dev/tty
