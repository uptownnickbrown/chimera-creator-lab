#!/bin/zsh
# Chimera Creator playtest launcher — run this in YOUR terminal so the game
# servers belong to you, not to a Claude session:   ./scripts/start_playtest.sh
# Stops cleanly with Ctrl-C (kills both servers).
set -e
ROOT=/Users/nbrown/Desktop/chimera-creator
PLAYTEST=/Users/nbrown/Desktop/chimera-playtest

CHIMERA_MEDIA_DIR=$ROOT/media \
DATABASE_URL="sqlite+aiosqlite:///$ROOT/chimera.db" \
  $ROOT/.venv/bin/uvicorn app.main:app --app-dir $PLAYTEST/backend \
  --port 8010 --log-level info &
BACK=$!

VITE_PROXY_TARGET=http://localhost:8010 \
  npm --prefix $PLAYTEST/frontend run dev -- --port 5175 --host --strictPort &
FRONT=$!

trap "kill $BACK $FRONT 2>/dev/null" EXIT INT TERM
echo ""
echo "  Chimera Creator playtest:  http://localhost:5175"
echo "  (iPad on your network:     http://$(ipconfig getifaddr en0 2>/dev/null || echo '<this-mac-ip>'):5175)"
echo "  Ctrl-C stops both servers."
echo ""
wait
