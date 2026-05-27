#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Setup BOTH Modes (Supabase + Plain PG) — Side by Side
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

COMPOSE_FILE="docker-compose.both.yml"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " AI Agent Platform — BOTH Modes Deployment"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "✗ Docker not found"; exit 1; }
[ -f .env ] || { echo "✗ .env not found. Run: bash scripts/generate_keys.sh > .env"; exit 1; }
echo "✓ Prerequisites OK"

# Source .env for migration
set -a; source .env; set +a

# ── Step 1: Start databases ─────────────────────────────────
echo ""
echo "[1/5] Starting databases..."
docker compose -f "$COMPOSE_FILE" up -d supabase-db plain-db

echo "   Waiting for databases to be healthy..."
for i in $(seq 1 30); do
    S_OK=$(docker inspect --format='{{.State.Health.Status}}' supabase-db 2>/dev/null || echo "none")
    P_OK=$(docker inspect --format='{{.State.Health.Status}}' plain-db 2>/dev/null || echo "none")
    if [ "$S_OK" = "healthy" ] && [ "$P_OK" = "healthy" ]; then
        echo "   ✓ Both databases ready (${i}s)"
        break
    fi
    sleep 1
done

# ── Step 2: Check supabase init schema ──────────────────────
echo ""
echo "[2/5] Verifying supabase-db schema..."
TABLE_COUNT=$(docker exec supabase-db psql -U postgres -t -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('profiles','providers','api_keys','chat_sessions','chat_messages','agents');" \
  2>/dev/null | tr -d ' ')

if [ "${TABLE_COUNT:-0}" -lt 6 ]; then
    echo "   ⏳ Schema still initializing, waiting 10s..."
    sleep 10
fi
echo "   ✓ Supabase schema OK"

# ── Step 3: Run auth migration on supabase-db ───────────────
echo ""
echo "[3/5] Running auth migration on supabase-db..."
if [ -f db/migrations/002_auth_references.sql ]; then
    docker exec -i supabase-db psql -U postgres < db/migrations/002_auth_references.sql 2>&1 | grep -E "^(CREATE|ALTER|DROP|DO|NOTICE)" || true
    echo "   ✓ Auth migration applied"
else
    echo "   ⚠ No auth migration file found, skipping"
fi

# ── Step 4: Start all services ──────────────────────────────
echo ""
echo "[4/5] Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "   Waiting for services to stabilize (30s)..."
sleep 30

# ── Step 5: Verify ──────────────────────────────────────────
echo ""
echo "[5/5] Verifying deployment..."
echo ""

SERVICES="supabase-db plain-db supabase-auth supabase-rest supabase-kong app-backend-supabase app-backend-plain nginx-proxy"
ALL_OK=true

for svc in $SERVICES; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null || echo "missing")
    if [ "$STATUS" = "running" ]; then
        echo "   ✓ $svc: running"
    else
        echo "   ✗ $svc: $STATUS"
        ALL_OK=false
    fi
done

echo ""
if $ALL_OK; then
    echo "═══════════════════════════════════════════════════════════"
    echo " ✓ BOTH MODES DEPLOYED SUCCESSFULLY"
    echo "═══════════════════════════════════════════════════════════"
else
    echo "═══════════════════════════════════════════════════════════"
    echo " ⚠ PARTIAL — Check failing services with:"
    echo "   docker compose -f $COMPOSE_FILE logs <service>"
    echo "═══════════════════════════════════════════════════════════"
fi

echo ""
echo "  Open: http://$(curl -s ifconfig.me 2>/dev/null || echo 'localhost')"
echo "  Toggle between Supabase PG and Plain PG on the login screen!"
echo ""
