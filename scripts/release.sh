#!/usr/bin/env bash
# Publie une release d'AuditErgo depuis ce poste, sans GitHub Actions (aucune minute consommée).
#
#   bash scripts/release.sh            # tests, exe, tag vX.Y.Z, release GitHub avec l'exe et le zip
#   bash scripts/release.sh --essai    # tout sauf le tag et la release : pour vérifier avant de publier
#   bash scripts/release.sh --brouillon      # release créée en brouillon, à publier depuis GitHub
#   bash scripts/release.sh --sans-tests     # saute les tests (déconseillé)
#
# À lancer sous Windows, dans Git Bash (installé avec Git pour Windows), depuis main à jour, après
# scripts/bump_version.py et la fusion sur main. Prérequis : Python 3.10+ et GitHub CLI (gh) connecté
# (`gh auth login`). Fait le même travail que le workflow « Build Windows exe » : voir README, « Versions ».
set -euo pipefail

ESSAI=0
BROUILLON=0
TESTS=1
for arg in "$@"; do
  case "$arg" in
    --essai) ESSAI=1 ;;
    --brouillon) BROUILLON=1 ;;
    --sans-tests) TESTS=0 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Option inconnue : $arg (voir --help)" >&2; exit 2 ;;
  esac
done

erreur() { echo "Erreur : $*" >&2; exit 1; }
etape() { echo; echo "==> $*"; }

cd "$(dirname "$0")/.."

# --- 1. Vérifications ------------------------------------------------------------------------------
etape "Vérifications"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *) erreur "l'exe Windows ne peut être fabriqué que sous Windows (lancer ce script dans Git Bash)." ;;
esac

VERSION="$(tr -d '[:space:]' < VERSION)"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || erreur "VERSION illisible : « $VERSION »."
TAG="v$VERSION"
echo "AuditErgo $VERSION (tag $TAG)"

if [ "$ESSAI" -eq 0 ]; then
  command -v gh >/dev/null || erreur "GitHub CLI (gh) introuvable : l'installer depuis https://cli.github.com puis lancer « gh auth login »."
  gh auth status >/dev/null 2>&1 || erreur "gh n'est pas connecté à GitHub : lancer « gh auth login »."

  branche="$(git rev-parse --abbrev-ref HEAD)"
  [ "$branche" = "main" ] || erreur "la release se fait depuis main (branche actuelle : $branche)."
  [ -z "$(git status --porcelain)" ] || erreur "des modifications ne sont pas committées (git status)."
  git fetch --quiet origin main --tags
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] \
    || erreur "main n'est pas à jour avec GitHub : lancer « git pull » (et « git push » si besoin)."
  if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    erreur "le tag $TAG existe déjà. Passer à la version suivante avec scripts/bump_version.py."
  fi
  grep -q "^## \[$VERSION\]" CHANGELOG.md \
    || erreur "CHANGELOG.md n'a pas de section « ## [$VERSION] » : lancer scripts/bump_version.py."
fi

# --- 2. Python de fabrication ----------------------------------------------------------------------
# Environnement isolé, propre à la release, pour ne pas toucher au .venv de start.bat.
etape "Environnement Python (.venv-release)"
if [ ! -x .venv-release/Scripts/python.exe ]; then
  if py -3 -c "import sys" >/dev/null 2>&1; then py -3 -m venv .venv-release
  elif python -c "import sys" >/dev/null 2>&1; then python -m venv .venv-release
  else erreur "Python introuvable : installer Python 3.10+ depuis https://www.python.org/downloads/."
  fi
fi
PY=.venv-release/Scripts/python.exe
"$PY" -m pip install --upgrade pip --disable-pip-version-check --quiet
"$PY" -m pip install -r requirements-dev.txt pyinstaller --disable-pip-version-check --quiet

# --- 3. Tests (remplacent le workflow « Tests ») -----------------------------------------------------
if [ "$TESTS" -eq 1 ]; then
  etape "Tests"
  "$PY" -m pytest -q
fi

# --- 4. Exe ----------------------------------------------------------------------------------------
etape "Fabrication de AuditErgo.exe"
[ -f web/dist/index.html ] || erreur "web/dist est absent : compiler l'interface (cd web && npm run build)."
"$PY" -m PyInstaller --noconfirm AuditErgo.spec

etape "Vérification de l'exe"
./dist/AuditErgo.exe --version
./dist/AuditErgo.exe --no-browser --port 8599 >/dev/null 2>&1 &
PID=$!
ok=0
for _ in $(seq 60); do
  if curl -sf http://127.0.0.1:8599/health >/dev/null; then ok=1; break; fi
  sleep 1
done
kill "$PID" 2>/dev/null || true
taskkill //F //IM AuditErgo.exe >/dev/null 2>&1 || true
[ "$ok" -eq 1 ] || erreur "l'exe ne répond pas sur /health."
echo "L'exe démarre et répond."

# --- 5. Fichiers de la release ---------------------------------------------------------------------
etape "Fichiers de la release"
EXE="dist/AuditErgo-$VERSION.exe"
BASE="AuditErgo-$VERSION-windows"
cp dist/AuditErgo.exe "$EXE"
# Zip à côté de l'exe : passe les filtres qui bloquent le téléchargement d'un .exe.
rm -rf dist/zip "dist/$BASE.zip"
mkdir -p "dist/zip/$BASE"
cp dist/AuditErgo.exe CHANGELOG.md .env.exemple "dist/zip/$BASE/"
(cd dist/zip && "../../$PY" -m zipfile -c "../$BASE.zip" "$BASE")
ZIP="dist/$BASE.zip"

# Notes : la section du journal pour cette version, suivie de la liste des PR générée par GitHub.
NOTES="dist/notes-$VERSION.md"
awk -v entete="## [$VERSION]" '
  index($0, entete) == 1 { dedans = 1; next }
  dedans && /^## \[/ { exit }
  dedans { print }
' CHANGELOG.md > "$NOTES"
echo "  $EXE"
echo "  $ZIP"
echo "  $NOTES"

if [ "$ESSAI" -eq 1 ]; then
  echo
  echo "Essai terminé : rien n'a été publié. Relancer sans --essai pour créer le tag et la release."
  exit 0
fi

# --- 6. Tag et release -----------------------------------------------------------------------------
etape "Tag $TAG et release GitHub"
git tag -a "$TAG" -m "AuditErgo $VERSION"
git push origin "$TAG"
options=(--verify-tag --title "AuditErgo $VERSION" --notes-file "$NOTES" --generate-notes)
[ "$BROUILLON" -eq 1 ] && options+=(--draft)
gh release create "$TAG" "${options[@]}" "$EXE" "$ZIP"

echo
if [ "$BROUILLON" -eq 1 ]; then
  echo "Brouillon créé : le relire et le publier depuis GitHub (Releases)."
else
  echo "Release $TAG publiée."
fi
