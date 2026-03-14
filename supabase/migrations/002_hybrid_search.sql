-- Migration: 002_hybrid_search.sql
-- Función hybrid_search() SQL con Reciprocal Rank Fusion
-- Fase 1 - Agentic RAG Platform

-- ============================================
-- FUNCIÓN: hybrid_search
-- Búsqueda híbrida: vectorial (HNSW) + full-text (BM25) + RRF
-- ============================================

CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    collection_ids uuid[] DEFAULT '{}'::uuid[],
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    source_id uuid,
    collection_id uuid,
    content text,
    metadata jsonb,
    created_at timestamptz,
    rrf_score double precision
) AS $$
BEGIN
    RETURN QUERY
    WITH 
    dense_results AS (
        SELECT 
            c.id,
            c.source_id,
            c.collection_id,
            c.content,
            c.metadata,
            c.created_at,
            1.0 / (ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) + 60) AS dense_rank
        FROM chunks c
        WHERE 
            c.embedding IS NOT NULL
            AND (array_length(collection_ids, 1) IS NULL OR c.collection_id = ANY(collection_ids))
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    fts_results AS (
        SELECT 
            c.id,
            c.source_id,
            c.collection_id,
            c.content,
            c.metadata,
            c.created_at,
            1.0 / (ROW_NUMBER() OVER (ORDER BY ts_rank(c.search_vec, plainto_tsquery('spanish', query_text)) DESC) + 60) AS fts_rank
        FROM chunks c
        WHERE 
            c.search_vec IS NOT NULL
            AND (array_length(collection_ids, 1) IS NULL OR c.collection_id = ANY(collection_ids))
            AND c.search_vec @@ plainto_tsquery('spanish', query_text)
        ORDER BY ts_rank(c.search_vec, plainto_tsquery('spanish', query_text)) DESC
        LIMIT match_count * 2
    ),
    combined AS (
        SELECT * FROM dense_results
        UNION ALL
        SELECT * FROM fts_results
    ),
    rrf_scored AS (
        SELECT 
            id,
            source_id,
            collection_id,
            content,
            metadata,
            created_at,
            SUM(dense_rank + fts_rank) AS rrf_score
        FROM (
            SELECT 
                id,
                source_id,
                collection_id,
                content,
                metadata,
                created_at,
                dense_rank,
                0.0 AS fts_rank
            FROM dense_results
            UNION ALL
            SELECT 
                id,
                source_id,
                collection_id,
                content,
                metadata,
                created_at,
                0.0 AS dense_rank,
                fts_rank
            FROM fts_results
        ) combined_ranks
        GROUP BY id, source_id, collection_id, content, metadata, created_at
    )
    SELECT 
        id,
        source_id,
        collection_id,
        content,
        metadata,
        created_at,
        rrf_score
    FROM rrf_scored
    ORDER BY rrf_score DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql
PARALLEL SAFE
STABLE;

-- ============================================
-- FUNCIÓN: simple_vector_search
-- Búsqueda solo vectorial (para casos simples)
-- ============================================

CREATE OR REPLACE FUNCTION simple_vector_search(
    query_embedding vector(1536),
    collection_ids uuid[] DEFAULT '{}'::uuid[],
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    source_id uuid,
    collection_id uuid,
    content text,
    metadata jsonb,
    created_at timestamptz,
    distance double precision
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.source_id,
        c.collection_id,
        c.content,
        c.metadata,
        c.created_at,
        (c.embedding <=> query_embedding) AS distance
    FROM chunks c
    WHERE 
        c.embedding IS NOT NULL
        AND (array_length(collection_ids, 1) IS NULL OR c.collection_id = ANY(collection_ids))
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql
PARALLEL SAFE
STABLE;

-- ============================================
-- FUNCIÓN: simple_fts_search
-- Búsqueda solo full-text (para casos simples)
-- ============================================

CREATE OR REPLACE FUNCTION simple_fts_search(
    query_text text,
    collection_ids uuid[] DEFAULT '{}'::uuid[],
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    source_id uuid,
    collection_id uuid,
    content text,
    metadata jsonb,
    created_at timestamptz,
    rank double precision
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.source_id,
        c.collection_id,
        c.content,
        c.metadata,
        c.created_at,
        ts_rank(c.search_vec, plainto_tsquery('spanish', query_text)) AS rank
    FROM chunks c
    WHERE 
        c.search_vec IS NOT NULL
        AND (array_length(collection_ids, 1) IS NULL OR c.collection_id = ANY(collection_ids))
        AND c.search_vec @@ plainto_tsquery('spanish', query_text)
    ORDER BY ts_rank(c.search_vec, plainto_tsquery('spanish', query_text)) DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql
PARALLEL SAFE
STABLE;

-- ============================================
-- GRANTS PARA LAS FUNCIONES
-- ============================================

GRANT EXECUTE ON FUNCTION hybrid_search(vector, text, uuid[], int) TO authenticated;
GRANT EXECUTE ON FUNCTION simple_vector_search(vector, uuid[], int) TO authenticated;
GRANT EXECUTE ON FUNCTION simple_fts_search(text, uuid[], int) TO authenticated;
