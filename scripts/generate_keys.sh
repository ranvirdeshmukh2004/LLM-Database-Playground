#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  generate_keys.sh — Generate all secrets for the AI Platform
#  Run once before first deployment.
#  Usage: bash scripts/generate_keys.sh > .env
# ═══════════════════════════════════════════════════════════════

set -e

echo "# ═══════════════════════════════════════════════════════"
echo "# MVP AI Agent Platform — Generated Secrets"
echo "# Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# ═══════════════════════════════════════════════════════"
echo ""

# ── 1. PostgreSQL ──────────────────────────────────────────
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
echo "# ── PostgreSQL ──────────────────────────────────────"
echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
echo "POSTGRES_HOST=supabase-db"
echo "POSTGRES_PORT=5432"
echo "POSTGRES_DB=postgres"
echo "POSTGRES_USER=postgres"
echo ""

# ── 2. JWT Secret ──────────────────────────────────────────
JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64)
echo "# ── JWT / Supabase Auth ────────────────────────────"
echo "JWT_SECRET=${JWT_SECRET}"
echo ""

# ── 3. Generate Supabase ANON_KEY and SERVICE_ROLE_KEY ─────
# These are JWTs signed with the JWT_SECRET
python3 -c "
import json, hmac, hashlib, base64, time

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def make_jwt(payload, secret):
    header = b64url(json.dumps({'alg':'HS256','typ':'JWT'}).encode())
    payload_b64 = b64url(json.dumps(payload).encode())
    signature_input = f'{header}.{payload_b64}'.encode()
    signature = hmac.new(secret.encode(), signature_input, hashlib.sha256).digest()
    sig_b64 = b64url(signature)
    return f'{header}.{payload_b64}.{sig_b64}'

secret = '${JWT_SECRET}'
iat = int(time.time())
exp = iat + (10 * 365 * 24 * 3600)  # 10 years

anon_payload = {'role': 'anon', 'iss': 'supabase', 'iat': iat, 'exp': exp}
service_payload = {'role': 'service_role', 'iss': 'supabase', 'iat': iat, 'exp': exp}

print(f'ANON_KEY={make_jwt(anon_payload, secret)}')
print(f'SERVICE_ROLE_KEY={make_jwt(service_payload, secret)}')
"
echo ""

# ── 4. Supabase Config ────────────────────────────────────
echo "# ── Supabase URLs ───────────────────────────────────"
echo "SUPABASE_URL=http://localhost:8000"
echo "API_EXTERNAL_URL=http://localhost:8000"
echo "SUPABASE_PUBLIC_URL=http://localhost:8000"
echo ""

echo "# ── Supabase Studio ─────────────────────────────────"
echo "STUDIO_PORT=3001"
echo "STUDIO_DEFAULT_ORGANIZATION=AI Platform"
echo "STUDIO_DEFAULT_PROJECT=MVP AI Agent Platform"
echo ""

echo "# ── Supabase Auth (GoTrue) ──────────────────────────"
echo "GOTRUE_SITE_URL=http://localhost:7860"
echo "GOTRUE_URI_ALLOW_LIST="
echo "GOTRUE_DISABLE_SIGNUP=false"
echo "GOTRUE_EXTERNAL_EMAIL_ENABLED=true"
echo "GOTRUE_MAILER_AUTOCONFIRM=true"
echo "GOTRUE_SMS_AUTOCONFIRM=true"
echo ""

# ── 5. App Encryption Key ────────────────────────────────
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)
echo "# ── App Secrets ─────────────────────────────────────"
echo "ENCRYPTION_KEY=${ENCRYPTION_KEY}"
APP_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
echo "APP_SECRET_KEY=${APP_SECRET}"
echo ""

echo "# ── External LLM Providers (user adds via UI) ──────"
echo "# These are optional system-level fallback keys"
echo "OPENROUTER_API_KEY="
echo "ANTHROPIC_API_KEY="
echo "XAI_API_KEY="
echo "OPENAI_API_KEY="
echo ""

echo "# ── App Config ──────────────────────────────────────"
echo "APP_HOST=0.0.0.0"
echo "APP_PORT=7860"
echo "LOG_LEVEL=info"
echo "ENVIRONMENT=development"
