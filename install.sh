#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
MAIN_FILE="$PROJECT_DIR/main.py"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
LAUNCHER_FILE="$VENV_DIR/bin/ai-dungeon"

echo "Preparing AI Dungeon CLI release..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 was not found in PATH."
    echo "Install Python 3 and run this script again."
    exit 1
fi

if [ ! -f "$MAIN_FILE" ]; then
    echo "Error: main.py was not found in $PROJECT_DIR."
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Upgrading pip..."
python -m pip install --upgrade pip

if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r "$REQUIREMENTS_FILE"
else
    echo "requirements.txt not found. Installing minimal runtime dependencies..."
    pip install requests PyYAML
fi

echo "Creating local ai-dungeon launcher..."
cat > "$LAUNCHER_FILE" <<'EOF'
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# shellcheck disable=SC1091
source "$PROJECT_DIR/venv/bin/activate"
exec python "$PROJECT_DIR/main.py" "$@"
EOF

chmod +x "$LAUNCHER_FILE"
chmod +x "$PROJECT_DIR/install.sh"

echo
echo "Installation complete."
echo "Run the project with:"
echo "  source \"$VENV_DIR/bin/activate\" && ai-dungeon"
echo
echo "Or without activating the environment:"
echo "  \"$LAUNCHER_FILE\""
echo
echo "Before running the client, export your backend key:"
echo "  export AIDUNGEON_FIREBASE_API_KEY=\"YOUR_FIREBASE_WEB_API_KEY\""
