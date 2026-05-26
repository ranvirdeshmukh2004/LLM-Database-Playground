-- ═══════════════════════════════════════════════════════════════
-- 002_app_users.sql — User credentials table for DB_MODE=plain
--
-- Replaces Supabase GoTrue's auth.users table.
-- The FastAPI app handles signup/login using bcrypt + self-signed JWTs.
-- ═══════════════════════════════════════════════════════════════

-- Ensure uuid-ossp is available (standard PostgreSQL, no Supabase needed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── App Users table ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.app_users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON public.app_users (email);

COMMENT ON TABLE public.app_users IS 'User credentials for plain PG mode (replaces GoTrue auth.users)';

-- ── Auto-create profile on user insert ──────────────────────
CREATE OR REPLACE FUNCTION public.handle_new_app_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name)
    VALUES (NEW.id, COALESCE(NEW.display_name, split_part(NEW.email, '@', 1)))
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_app_user_created ON public.app_users;
CREATE TRIGGER on_app_user_created
    AFTER INSERT ON public.app_users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_app_user();
