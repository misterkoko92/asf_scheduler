#!/usr/bin/env bash
set -e

APP_NAME="ASF Scheduler"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LAUNCHER="launcher.py"
DMG_NAME="ASF-Scheduler.dmg"
RELEASE_DIR="$PROJECT_DIR/release"

echo ""
echo "=== BUILD ASF SCHEDULER (Python 3.11) ==="
echo "Projet : $PROJECT_DIR"
echo ""

# 1) Activer venv
source "$VENV_DIR/bin/activate"

# 2) Installer PyInstaller si absent
pip install pyinstaller

echo ""
echo "=== Étape 1 : Build .app ==="

rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist"

pyinstaller \
  --name "$APP_NAME" \
  --windowed \
  --noconfirm \
  --hidden-import streamlit \
  --hidden-import streamlit.web.cli \
  --add-data "asf_app:asf_app" \
  --add-data "scheduler:scheduler" \
  --add-data "loaders:loaders" \
  --add-data "api:api" \
  --add-data "data:data" \
  --add-data "planning_resultats:planning_resultats" \
  "$LAUNCHER"

echo ""
echo "=== Étape 2 : Préparer dossier release ==="
mkdir -p "$RELEASE_DIR"

rm -rf "$RELEASE_DIR/$APP_NAME.app"
cp -R "$PROJECT_DIR/dist/$APP_NAME.app" "$RELEASE_DIR/"

echo "App copiée dans : $RELEASE_DIR/$APP_NAME.app"

# 3) Vérifier presence create-dmg
if ! command -v create-dmg >/dev/null 2>&1; then
  echo "❌ create-dmg non installé"
  echo "Installe-le : brew install create-dmg"
  exit 1
fi

echo ""
echo "=== Étape 3 : Créer le .dmg ==="
cd "$PROJECT_DIR"
rm -f "$DMG_NAME"

create-dmg \
  --volname "$APP_NAME" \
  --window-size 500 300 \
  --icon "$APP_NAME.app" 125 150 \
  --app-drop-link 375 150 \
  "$DMG_NAME" \
  "$RELEASE_DIR/"

echo ""
echo "🎉 Build terminé !"
echo "DMG : $PROJECT_DIR/$DMG_NAME"
