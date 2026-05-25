-- ═══════════════════════════════════════════════════════════════
-- MVP AI Agent Platform — PostgreSQL Init Schema (001)
-- Runs via docker-entrypoint-initdb.d/ on FIRST DB startup.
--
-- IMPORTANT: At init time, the 'auth' schema does NOT exist yet
-- (GoTrue creates it when it first connects). So we CANNOT reference
-- auth.users or auth.uid() here.
--
-- Tables use plain UUID columns for user_id.
-- auth.users foreign keys + RLS policies are added in 002 (post-init).
-- ═══════════════════════════════════════════════════════════════

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ═══════════════════════════════════════════════════════════════
-- 1. USER PROFILES
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.profiles (
    id            UUID PRIMARY KEY,
    display_name  TEXT,
    avatar_url    TEXT,
    preferences   JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.profiles IS 'Extended user profile data, linked 1:1 with auth.users (FK added post-init)';


-- ═══════════════════════════════════════════════════════════════
-- 2. API KEYS (Encrypted at application layer)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.api_keys (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL,
    provider      TEXT NOT NULL,
    key_name      TEXT NOT NULL DEFAULT 'default',
    encrypted_key TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    last_used_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider, key_name)
);

COMMENT ON TABLE public.api_keys IS 'User-provided LLM API keys, encrypted with Fernet at app layer';


-- ═══════════════════════════════════════════════════════════════
-- 3. CHAT SESSIONS
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL,
    title         TEXT DEFAULT 'New Chat',
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    system_prompt TEXT DEFAULT 'You are a helpful AI assistant.',
    settings      JSONB DEFAULT '{"temperature": 0.7, "max_tokens": 2048, "top_p": 0.9}',
    is_archived   BOOLEAN DEFAULT FALSE,
    message_count INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.chat_sessions IS 'Chat conversation sessions with per-session model/provider config';


-- ═══════════════════════════════════════════════════════════════
-- 4. CHAT MESSAGES
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id    UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content       TEXT NOT NULL,
    token_count   INTEGER,
    latency_ms    INTEGER,
    model         TEXT,
    provider      TEXT,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.chat_messages IS 'Individual messages within a chat session';


-- ═══════════════════════════════════════════════════════════════
-- 5. AGENT CONFIGURATIONS
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    system_prompt   TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    settings        JSONB DEFAULT '{"temperature": 0.7, "max_tokens": 2048}',
    tools           JSONB DEFAULT '[]',
    is_public       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE public.agents IS 'User-created AI agent configurations with custom prompts and settings';


-- ═══════════════════════════════════════════════════════════════
-- 6. PROVIDER REGISTRY (System-level, seeded data)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.providers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    base_url      TEXT NOT NULL,
    api_type      TEXT NOT NULL DEFAULT 'openai',
    auth_header   TEXT DEFAULT 'Authorization',
    auth_prefix   TEXT DEFAULT 'Bearer',
    models        JSONB DEFAULT '[]',
    is_active     BOOLEAN DEFAULT TRUE,
    metadata      JSONB DEFAULT '{}'
);

COMMENT ON TABLE public.providers IS 'System-level LLM provider registry with available models';

-- Seed default providers
INSERT INTO public.providers (id, name, base_url, api_type, auth_header, auth_prefix, models, metadata)
VALUES
    ('openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1', 'openai', 'Authorization', 'Bearer',
     '[{"id":"google/gemini-2.5-pro-preview","name":"Gemini 2.5 Pro","context":1048576},
       {"id":"anthropic/claude-sonnet-4","name":"Claude Sonnet 4","context":200000},
       {"id":"meta-llama/llama-4-maverick","name":"Llama 4 Maverick","context":1048576},
       {"id":"openai/gpt-4o","name":"GPT-4o","context":128000},
       {"id":"deepseek/deepseek-r1","name":"DeepSeek R1","context":163840},
       {"id":"qwen/qwen3-235b-a22b","name":"Qwen3 235B","context":40960}]',
     '{"extra_headers":{"HTTP-Referer":"https://ai-agent-platform.local","X-Title":"AI Agent Platform"}}'),

    ('anthropic', 'Anthropic (Claude)', 'https://api.anthropic.com/v1', 'anthropic', 'x-api-key', '',
     '[{"id":"claude-sonnet-4-20250514","name":"Claude Sonnet 4","context":200000},
       {"id":"claude-haiku-3-5-20241022","name":"Claude 3.5 Haiku","context":200000},
       {"id":"claude-opus-4-20250514","name":"Claude Opus 4","context":200000}]',
     '{"api_version":"2023-06-01"}'),

    ('xai', 'xAI (Grok)', 'https://api.x.ai/v1', 'openai', 'Authorization', 'Bearer',
     '[{"id":"grok-3","name":"Grok 3","context":131072},
       {"id":"grok-3-mini","name":"Grok 3 Mini","context":131072}]',
     '{}'),

    ('openai', 'OpenAI', 'https://api.openai.com/v1', 'openai', 'Authorization', 'Bearer',
     '[{"id":"gpt-4o","name":"GPT-4o","context":128000},
       {"id":"gpt-4o-mini","name":"GPT-4o Mini","context":128000},
       {"id":"o3-mini","name":"o3-mini","context":200000}]',
     '{}'),

    ('custom', 'Self-Hosted', 'http://localhost:8080', 'custom', '', '',
     '[]',
     '{"description":"Self-hosted models on your own EC2 instances"}')
ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════
-- 7. INDEXES
-- ═══════════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_provider ON public.api_keys(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON public.chat_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON public.chat_sessions(user_id) WHERE NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_messages_session ON public.chat_messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user ON public.chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_agents_user ON public.agents(user_id);


-- ═══════════════════════════════════════════════════════════════
-- 8. TRIGGERS — Auto-update updated_at
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profiles_updated ON public.profiles;
CREATE TRIGGER trg_profiles_updated BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_api_keys_updated ON public.api_keys;
CREATE TRIGGER trg_api_keys_updated BEFORE UPDATE ON public.api_keys
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_sessions_updated ON public.chat_sessions;
CREATE TRIGGER trg_sessions_updated BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

DROP TRIGGER IF EXISTS trg_agents_updated ON public.agents;
CREATE TRIGGER trg_agents_updated BEFORE UPDATE ON public.agents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


-- ═══════════════════════════════════════════════════════════════
-- 9. MESSAGE COUNT TRIGGER
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.increment_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE public.chat_sessions
    SET message_count = message_count + 1,
        updated_at = NOW()
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_increment_msg_count ON public.chat_messages;
CREATE TRIGGER trg_increment_msg_count
    AFTER INSERT ON public.chat_messages
    FOR EACH ROW EXECUTE FUNCTION public.increment_message_count();
