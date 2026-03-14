-- Migration: 001_initial.sql
-- Tablas base + pgvector + HNSW
-- Fase 1 - Agentic RAG Platform

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- TABLE: collections
-- Espacios de conocimiento del usuario
-- ============================================
CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready', 'indexing', 'error')),
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TABLE: sources
-- Fuentes individuales dentro de una colección
-- ============================================
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('file', 'url')),
    name TEXT NOT NULL,
    original_path TEXT,
    url TEXT,
    file_size BIGINT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'indexing', 'ready', 'error')),
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TABLE: chunks
-- Fragmentos con embeddings
-- ============================================
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),
    search_vec tsvector,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TABLE: indexing_jobs
-- Cola de trabajos asíncronos
-- ============================================
CREATE TABLE IF NOT EXISTS indexing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TABLE: conversations
-- Historial de chat
-- ============================================
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    collection_ids UUID[] DEFAULT '{}'::uuid[],
    title TEXT,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TABLE: messages
-- Mensajes individuales
-- ============================================
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- INDICES CRÍTICOS
-- ============================================

-- HNSW index para búsqueda vectorial (cosine distance)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
    ON chunks USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64);

-- GIN index para full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_search_vec_gin 
    ON chunks USING gin(search_vec);

-- Índice para filtrado por colección
CREATE INDEX IF NOT EXISTS idx_chunks_collection_id 
    ON chunks (collection_id);

-- Índice para filtrado por tipo de archivo (metadata->>'file_ext')
CREATE INDEX IF NOT EXISTS idx_chunks_file_ext 
    ON chunks (((metadata->>'file_ext')));

-- Índice para filtrado de sources por colección
CREATE INDEX IF NOT EXISTS idx_sources_collection_id 
    ON sources (collection_id);

-- Índice para filtrado de indexing_jobs por colección
CREATE INDEX IF NOT EXISTS idx_indexing_jobs_collection_id 
    ON indexing_jobs (collection_id);

-- Índice para filtrado de conversaciones por usuario
CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
    ON conversations (user_id);

-- Índice para filtrado de mensajes por conversación
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
    ON messages (conversation_id);

-- Índice para búsqueda de colecciones por usuario y status
CREATE INDEX IF NOT EXISTS idx_collections_user_id_status 
    ON collections (user_id, status);

-- ============================================
-- TRIGGERS AUTOMÁTICOS
-- ============================================

-- Trigger para actualizar search_vec (tsvector) automáticamente
CREATE OR REPLACE FUNCTION chunks_search_vec_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.search_vec := to_tsvector('spanish', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chunks_search_vec_update ON chunks;
CREATE TRIGGER chunks_search_vec_update
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION chunks_search_vec_trigger();

-- Trigger para actualizar updated_at en conversaciones
CREATE OR REPLACE FUNCTION conversations_updated_at_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS conversations_updated_at_update ON conversations;
CREATE TRIGGER conversations_updated_at_update
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION conversations_updated_at_trigger();

-- ============================================
-- FUNCIONES AUXILIARES
-- ============================================

-- Función para actualizar chunk_count en collections
CREATE OR REPLACE FUNCTION update_collection_chunk_count()
RETURNS trigger AS $$
DECLARE
    target_collection_id UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_collection_id := OLD.collection_id;
    ELSE
        target_collection_id := NEW.collection_id;
    END IF;

    UPDATE collections 
    SET chunk_count = (
        SELECT COUNT(*) 
        FROM chunks 
        WHERE collection_id = target_collection_id
    )
    WHERE id = target_collection_id;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para mantener chunk_count actualizado
DROP TRIGGER IF EXISTS chunks_collection_count_update ON chunks;
CREATE TRIGGER chunks_collection_count_update
    AFTER INSERT OR DELETE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_collection_chunk_count();
