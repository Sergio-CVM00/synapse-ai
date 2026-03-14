-- Migration: 003_rls_policies.sql
-- Row Level Security (RLS) Policies
-- Fase 1 - Agentic RAG Platform

-- ============================================
-- ENABLE RLS ON ALL TABLES
-- ============================================

ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE indexing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- ============================================
-- COLLECTIONS POLICIES
-- ============================================

-- Users can view their own collections
CREATE POLICY "Users can view their own collections"
    ON collections FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own collections
CREATE POLICY "Users can insert their own collections"
    ON collections FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own collections
CREATE POLICY "Users can update their own collections"
    ON collections FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own collections
CREATE POLICY "Users can delete their own collections"
    ON collections FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================
-- SOURCES POLICIES
-- ============================================

-- Users can view sources from their collections
CREATE POLICY "Users can view sources from their collections"
    ON sources FOR SELECT
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- Users can insert sources into their collections
CREATE POLICY "Users can insert sources into their collections"
    ON sources FOR INSERT
    WITH CHECK (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- Users can update sources from their collections
CREATE POLICY "Users can update sources from their collections"
    ON sources FOR UPDATE
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- Users can delete sources from their collections
CREATE POLICY "Users can delete sources from their collections"
    ON sources FOR DELETE
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- ============================================
-- CHUNKS POLICIES
-- ============================================

-- Users can view chunks from their collections
CREATE POLICY "Users can view chunks from their collections"
    ON chunks FOR SELECT
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- Service role can insert chunks (for ingestion pipeline)
CREATE POLICY "Service role can insert chunks"
    ON chunks FOR INSERT
    WITH CHECK (true);

-- Service role can update chunks
CREATE POLICY "Service role can update chunks"
    ON chunks FOR UPDATE
    USING (true);

-- Users can delete chunks from their collections (via collection delete)
CREATE POLICY "Users can delete chunks from their collections"
    ON chunks FOR DELETE
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- ============================================
-- INDEXING_JOBS POLICIES
-- ============================================

-- Users can view indexing jobs from their collections
CREATE POLICY "Users can view indexing jobs from their collections"
    ON indexing_jobs FOR SELECT
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- Service role can insert indexing jobs
CREATE POLICY "Service role can insert indexing jobs"
    ON indexing_jobs FOR INSERT
    WITH CHECK (true);

-- Service role can update indexing jobs
CREATE POLICY "Service role can update indexing jobs"
    ON indexing_jobs FOR UPDATE
    USING (true);

-- Users can delete indexing jobs from their collections
CREATE POLICY "Users can delete indexing jobs from their collections"
    ON indexing_jobs FOR DELETE
    USING (
        collection_id IN (
            SELECT id FROM collections WHERE user_id = auth.uid()
        )
    );

-- ============================================
-- CONVERSATIONS POLICIES
-- ============================================

-- Users can view their own conversations
CREATE POLICY "Users can view their own conversations"
    ON conversations FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own conversations
CREATE POLICY "Users can insert their own conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own conversations
CREATE POLICY "Users can update their own conversations"
    ON conversations FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own conversations
CREATE POLICY "Users can delete their own conversations"
    ON conversations FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================
-- MESSAGES POLICIES
-- ============================================

-- Users can view messages from their conversations
CREATE POLICY "Users can view messages from their conversations"
    ON messages FOR SELECT
    USING (
        conversation_id IN (
            SELECT id FROM conversations WHERE user_id = auth.uid()
        )
    );

-- Users can insert messages into their conversations
CREATE POLICY "Users can insert messages into their conversations"
    ON messages FOR INSERT
    WITH CHECK (
        conversation_id IN (
            SELECT id FROM conversations WHERE user_id = auth.uid()
        )
    );

-- Users can delete messages from their conversations
CREATE POLICY "Users can delete messages from their conversations"
    ON messages FOR DELETE
    USING (
        conversation_id IN (
            SELECT id FROM conversations WHERE user_id = auth.uid()
        )
    );

-- ============================================
-- ADDITIONAL SECURITY: FUNCTION GRANTS
-- ============================================

-- Grant execute on hybrid_search to authenticated users
GRANT EXECUTE ON FUNCTION hybrid_search TO authenticated;

-- Grant select on tables needed for service role operations
GRANT SELECT ON collections TO service_role;
GRANT SELECT ON sources TO service_role;
GRANT SELECT ON chunks TO service_role;
GRANT SELECT ON indexing_jobs TO service_role;
GRANT SELECT ON conversations TO service_role;
GRANT SELECT ON messages TO service_role;

-- Grant insert/update/delete on tables needed for service role
GRANT INSERT, UPDATE, DELETE ON collections TO service_role;
GRANT INSERT, UPDATE, DELETE ON sources TO service_role;
GRANT INSERT, UPDATE, DELETE ON chunks TO service_role;
GRANT INSERT, UPDATE, DELETE ON indexing_jobs TO service_role;
GRANT INSERT, UPDATE, DELETE ON conversations TO service_role;
GRANT INSERT, UPDATE, DELETE ON messages TO service_role;

-- ============================================
-- BANDEJA DE ENTRADA (OPTIONAL - para futuras versiones)
-- ============================================

-- Nota: La tabla auth.users ya tiene sus propias políticas de Supabase.
-- No modificamos auth schema para mantener compatibilidad.
