-- ═══════════════════════════════════════════════════════════════
-- MVP AI Agent Platform — Post-Init Migration (002)
--
-- This script runs AFTER GoTrue has created the auth schema.
-- Run manually: docker exec -i supabase-db psql -U postgres -d postgres < db/post-init/002_auth_references.sql
-- Or via the setup script: bash scripts/setup.sh
--
-- Adds:
--   - Foreign key constraints to auth.users
--   - RLS policies using auth.uid()
--   - Profile auto-creation trigger
-- ═══════════════════════════════════════════════════════════════

-- Wait / verify auth schema exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'auth') THEN
        RAISE EXCEPTION 'auth schema does not exist yet. Run this after GoTrue has started.';
    END IF;
END
$$;


-- ═══════════════════════════════════════════════════════════════
-- 1. ADD FOREIGN KEYS TO auth.users
-- ═══════════════════════════════════════════════════════════════

-- profiles.id → auth.users.id
DO $$ BEGIN
    ALTER TABLE public.profiles
        ADD CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- api_keys.user_id → auth.users.id
DO $$ BEGIN
    ALTER TABLE public.api_keys
        ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- chat_sessions.user_id → auth.users.id
DO $$ BEGIN
    ALTER TABLE public.chat_sessions
        ADD CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- chat_messages.user_id → auth.users.id
DO $$ BEGIN
    ALTER TABLE public.chat_messages
        ADD CONSTRAINT chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- agents.user_id → auth.users.id
DO $$ BEGIN
    ALTER TABLE public.agents
        ADD CONSTRAINT agents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ═══════════════════════════════════════════════════════════════
-- 2. PROFILE AUTO-CREATE TRIGGER
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ═══════════════════════════════════════════════════════════════
-- 3. ROW-LEVEL SECURITY (RLS) — Using auth.uid()
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;

-- Profiles: users manage their own
DROP POLICY IF EXISTS "Users manage own profile" ON public.profiles;
CREATE POLICY "Users manage own profile"
    ON public.profiles FOR ALL
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- API Keys: users manage their own
DROP POLICY IF EXISTS "Users manage own API keys" ON public.api_keys;
CREATE POLICY "Users manage own API keys"
    ON public.api_keys FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Chat Sessions: users manage their own
DROP POLICY IF EXISTS "Users manage own sessions" ON public.chat_sessions;
CREATE POLICY "Users manage own sessions"
    ON public.chat_sessions FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Chat Messages: users manage their own
DROP POLICY IF EXISTS "Users manage own messages" ON public.chat_messages;
CREATE POLICY "Users manage own messages"
    ON public.chat_messages FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Agents: users manage own, read public
DROP POLICY IF EXISTS "Users manage own agents" ON public.agents;
CREATE POLICY "Users manage own agents"
    ON public.agents FOR ALL
    USING (auth.uid() = user_id OR is_public = TRUE)
    WITH CHECK (auth.uid() = user_id);

-- Providers: readable by all authenticated users
DROP POLICY IF EXISTS "Anyone can read providers" ON public.providers;
CREATE POLICY "Anyone can read providers"
    ON public.providers FOR SELECT
    USING (TRUE);


-- ═══════════════════════════════════════════════════════════════
-- DONE
-- ═══════════════════════════════════════════════════════════════
DO $$ BEGIN RAISE NOTICE '✓ Auth references, RLS policies, and triggers applied successfully.'; END $$;
