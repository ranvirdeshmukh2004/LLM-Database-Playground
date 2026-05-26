#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 000_roles.sh — Create Supabase system roles
# Runs BEFORE 001_initial_schema.sql (alphabetical order)
#
# Shell script used instead of .sql because we need reliable
# access to the POSTGRES_PASSWORD environment variable to set
# role passwords.
# ═══════════════════════════════════════════════════════════════

set -e

echo "=== Creating Supabase system roles ==="

psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL

    -- ── Create roles ─────────────────────────────────────────
    DO \$\$ BEGIN CREATE ROLE supabase_admin LOGIN SUPERUSER PASSWORD '$POSTGRES_PASSWORD'; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE supabase_auth_admin NOINHERIT LOGIN CREATEROLE CREATEDB PASSWORD '$POSTGRES_PASSWORD'; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE supabase_storage_admin NOINHERIT LOGIN PASSWORD '$POSTGRES_PASSWORD'; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD '$POSTGRES_PASSWORD'; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE anon NOLOGIN NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE authenticated NOLOGIN NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;
    DO \$\$ BEGIN CREATE ROLE dashboard_user NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END \$\$;

    -- ── Create schemas needed by Supabase services ─────────
    CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;
    CREATE SCHEMA IF NOT EXISTS storage AUTHORIZATION supabase_storage_admin;
    CREATE SCHEMA IF NOT EXISTS extensions;

    -- ── Grant memberships ────────────────────────────────────
    GRANT anon TO authenticator;
    GRANT authenticated TO authenticator;
    GRANT service_role TO authenticator;
    GRANT supabase_admin TO authenticator;
    GRANT anon TO supabase_storage_admin;
    GRANT authenticated TO supabase_storage_admin;

    -- ── Schema permissions ───────────────────────────────────
    GRANT CREATE ON DATABASE postgres TO supabase_auth_admin;
    GRANT CREATE ON DATABASE postgres TO supabase_storage_admin;
    GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
    GRANT ALL ON SCHEMA public TO supabase_admin, supabase_auth_admin, supabase_storage_admin;
    GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role, supabase_admin;
    GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
    GRANT USAGE ON SCHEMA storage TO anon, authenticated, service_role;
    GRANT ALL ON SCHEMA storage TO supabase_storage_admin;

    -- Default privileges for tables created in public
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon, authenticated, service_role;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, UPDATE, DELETE ON TABLES TO authenticated, service_role;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO anon, authenticated, service_role;

    -- Default privileges for auth schema (so PostgREST can read auth.users)
    ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT SELECT ON TABLES TO postgres, anon, authenticated, service_role;
    ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT USAGE, SELECT ON SEQUENCES TO postgres, anon, authenticated, service_role;

    -- Auth admin search path
    ALTER ROLE supabase_auth_admin SET search_path TO auth, public;

EOSQL

echo "=== Supabase roles created successfully ==="
