#!/bin/bash
set -e

REPO="https://github.com/surfeedai-dev/timerch"
INSTALL_DIR="$HOME/타임캐릭터"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  타임캐릭터 설치를 시작합니다 🐾"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Python 확인
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3가 설치되어 있지 않습니다."
    echo "   https://www.python.org 에서 설치 후 다시 실행해주세요."
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_VER" -lt 9 ]; then
    echo "❌ Python 3.9 이상이 필요합니다. (현재: 3.$PY_VER)"
    exit 1
fi

# 2. git 확인
if ! command -v git &>/dev/null; then
    echo "❌ git이 설치되어 있지 않습니다."
    echo "   터미널에서 'xcode-select --install' 실행 후 다시 시도해주세요."
    exit 1
fi

# 3. 다운로드
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 기존 설치 폴더 발견 → 최신 버전으로 업데이트합니다."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo "📥 다운로드 중..."
    git clone --quiet "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 4. 가상환경 & 패키지 설치
if [ ! -d "venv" ]; then
    echo "🔧 환경 설정 중... (최초 1회, 1~3분 소요)"
    python3 -m venv venv
    ./venv/bin/pip install --quiet --upgrade pip
    ./venv/bin/pip install --quiet pyobjc
    echo "✅ 설치 완료!"
else
    echo "✅ 이미 설치되어 있습니다."
fi

# 5. 바탕화면에 실행 파일 생성
LAUNCHER="$HOME/Desktop/타임캐릭터.command"
cat > "$LAUNCHER" << 'LAUNCH'
#!/bin/bash
cd "$HOME/타임캐릭터"
./venv/bin/python app_native.py
LAUNCH
chmod +x "$LAUNCHER"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  설치 완료! 🎉"
echo ""
echo "  실행 방법:"
echo "  바탕화면의 '타임캐릭터.command' 파일을 더블클릭"
echo ""
echo "  ⚠️  최초 실행 시 macOS 보안 설정 필요:"
echo "  시스템 설정 → 개인 정보 보호 및 보안"
echo "  → 손쉬운 사용 → 터미널 허용"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
