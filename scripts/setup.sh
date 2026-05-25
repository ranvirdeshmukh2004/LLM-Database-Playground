#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  setup.sh — Full deployment setup for EC2
#
#  Usage: bash scripts/setup.sh
#
#  This script:
#    1. Starts PostgreSQL first (alone)
#    2. Waits for it to be healthy
#    3. Starts GoTrue (creates auth schema)
#    4. Waits for auth to be healthy
#    5. Runs post-init migration (auth FKs + RLS)
#    6. Starts remaining services
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════"
echo " AI Agent Platform — Deployment Setup"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Check prerequisites ───────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed.${NC}"
    echo "Run: curl -fsSL https://get.docker.com | sudo sh"
    exit 1
fi

if [ ! -f .env ]; then
    echo -e "${RED}ERROR: .env file not found.${NC}"
    echo "Run: bash scripts/generate_keys.sh > .env"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker found"
echo -e "${GREEN}✓${NC} .env file found"
echo ""

# ── Step 1: Start PostgreSQL only ─────────────────────────────
echo -e "${YELLOW}[1/6]${NC} Starting PostgreSQL..."
docker compose up -d supabase-db
echo "   Waiting for PostgreSQL to be healthy..."

for i in $(seq 1 60); do
    if docker exec supabase-db pg_isready -U postgres > /dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} PostgreSQL is ready (${i}s)"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "   ${RED}✗ PostgreSQL failed to start in 60s${NC}"
        echo "   Check logs: docker compose logs supabase-db"
        exit 1
    fi
    sleep 1
done

# Small extra wait for init scripts to complete
sleep 3

# ── Step 2: Verify init schema ──────────────────────────────
echo -e "${YELLOW}[2/6]${NC} Verifying init schema..."
TABLE_COUNT=$(docker exec supabase-db psql -U postgres -d postgres -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('profiles','api_keys','chat_sessions','chat_messages','agents','providers');")
TABLE_COUNT=$(echo "$TABLE_COUNT" | tr -d ' ')

if [ "$TABLE_COUNT" -ge 6 ]; then
    echo -e "   ${GREEN}✓${NC} All 6 tables created"
else
    echo -e "   ${YELLOW}!${NC} Only $TABLE_COUNT/6 tables found, init may still be running..."
    sleep 5
fi

# ── Step 3: Start GoTrue (creates auth schema) ───────────────
echo -e "${YELLOW}[3/6]${NC} Starting GoTrue (auth service)..."
docker compose up -d supabase-auth
echo "   Waiting for auth to be healthy..."

for i in $(seq 1 90); do
    if docker exec supabase-auth wget --no-verbose --tries=1 --spider http://localhost:9999/health > /dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} GoTrue is ready (${i}s)"
        break
    fi
    if [ $i -eq 90 ]; then
        echo -e "   ${RED}✗ GoTrue failed to start in 90s${NC}"
        echo "   Check logs: docker compose logs supabase-auth"
        exit 1
    fi
    sleep 1
done

# ── Step 4: Run post-init migration ─────────────────────────
echo -e "${YELLOW}[4/6]${NC} Running auth migration (FKs + RLS)..."
docker exec -i supabase-db psql -U postgres -d postgres < db/post-init/002_auth_references.sql

if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} Auth references and RLS policies applied"
else
    echo -e "   ${RED}✗ Post-init migration failed${NC}"
    echo "   You can re-run it manually:"
    echo "   docker exec -i supabase-db psql -U postgres -d postgres < db/post-init/002_auth_references.sql"
fi

# ── Step 5: Start remaining services ─────────────────────────
echo -e "${YELLOW}[5/6]${NC} Starting all remaining services..."
docker compose up -d

echo "   Waiting for services to stabilize (30s)..."
sleep 30

# ── Step 6: Verify ───────────────────────────────────────────
echo -e "${YELLOW}[6/6]${NC} Verifying deployment..."
echo ""

# Check each service
SERVICES=("supabase-db" "supabase-auth" "supabase-rest" "supabase-kong" "supabase-realtime" "supabase-storage" "supabase-meta" "supabase-studio" "app-backend" "nginx-proxy")

ALL_OK=true
for svc in "${SERVICES[@]}"; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null || echo "not found")
    if [ "$STATUS" = "running" ]; then
        echo -e "   ${GREEN}✓${NC} $svc: running"
    else
        echo -e "   ${RED}✗${NC} $svc: $STATUS"
        ALL_OK=false
    fi
done

echo ""

# Get the EC2 public IP
PUBLIC_IP=$(curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")

if $ALL_OK; then
    echo "═══════════════════════════════════════════════════════════"
    echo -e " ${GREEN}✓ DEPLOYMENT SUCCESSFUL!${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Platform:      http://${PUBLIC_IP}"
    echo "  API Docs:      http://${PUBLIC_IP}/docs"
    echo "  Supabase API:  http://${PUBLIC_IP}:8080"
    echo "  Health:        http://${PUBLIC_IP}/health"
    echo ""
    echo "  Next steps:"
    echo "    1. Open http://${PUBLIC_IP} in your browser"
    echo "    2. Sign up for an account"
    echo "    3. Add your API keys (OpenRouter, Claude, etc.)"
    echo "    4. Start chatting!"
    echo ""
else
    echo "═══════════════════════════════════════════════════════════"
    echo -e " ${YELLOW}⚠ PARTIAL DEPLOYMENT — Some services need attention${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Check failing services:"
    echo "    docker compose logs <service-name>"
    echo ""
    echo "  Restart everything:"
    echo "    docker compose restart"
    echo ""
fi
