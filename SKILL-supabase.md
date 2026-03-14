# SKILL: Supabase + pgvector en este proyecto

> Consultar antes de cualquier tarea que toque la base de datos, migraciones, RLS, o queries vectoriales.

---

## Cliente correcto según contexto

```typescript
// Browser / componentes cliente
import { createBrowserClient } from '@supabase/ssr'
// Usar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY
// Solo lee datos del usuario autenticado (RLS activo)

// Server Functions / API handlers (Nitro)
import { createServerClient } from '@supabase/ssr'
// Usar SUPABASE_SERVICE_ROLE_KEY — bypasea RLS
// NUNCA exponer en variables VITE_* ni al cliente
```

**Regla:** Si el código puede llegar al navegador → `anon key`. Si corre solo en servidor → `service role`.

---

## Hybrid search — cómo llamarla

```typescript
// Desde Server Function en apps/web/app/server/chat.ts
const { data: chunks } = await supabase.rpc('hybrid_search', {
  query_embedding: embeddingArray,   // number[] de 1536 dims
  query_text: userQuery,
  collection_ids: ['uuid1', 'uuid2'],
  match_count: 15,
})
```

La función retorna filas con: `id`, `content`, `metadata`, `rrf_score`, `source_id`.

Desde Python (agente):
```python
result = supabase.rpc('hybrid_search', {
    'query_embedding': embedding_list,
    'query_text': query,
    'collection_ids': collection_ids,
    'match_count': 15,
}).execute()
chunks = result.data
```

---

## Insertar chunks con embedding

```python
# apps/agent/db/supabase.py
# Insertar en batches de 100 para no saturar

rows = [
    {
        'source_id': source_id,
        'collection_id': collection_id,
        'content': chunk.text,
        'embedding': chunk.embedding,        # list[float] de 1536
        'metadata': {
            'file_path': chunk.file_path,
            'start_line': chunk.start_line,
            'end_line': chunk.end_line,
            'file_ext': chunk.file_ext,
            'url': chunk.url,               # None si es archivo local
            'heading': chunk.heading,        # None si no aplica
        }
    }
    for chunk in batch
]

supabase.table('chunks').insert(rows).execute()

# search_vec se genera automáticamente via trigger SQL:
# to_tsvector('english', content)
```

---

## RLS policies — patrón estándar

Todas las tablas usan el mismo patrón. El `user_id` de la sesión activa filtra los datos:

```sql
-- Ejemplo para tabla 'collections'
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users see own collections"
  ON collections FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "users insert own collections"
  ON collections FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users update own collections"
  ON collections FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "users delete own collections"
  ON collections FOR DELETE
  USING (user_id = auth.uid());
```

Para `chunks` (sin `user_id` directo, hereda de `collections`):
```sql
CREATE POLICY "users see own chunks"
  ON chunks FOR SELECT
  USING (
    collection_id IN (
      SELECT id FROM collections WHERE user_id = auth.uid()
    )
  );
```

---

## Migraciones — flujo de trabajo

```bash
# Local
supabase start                    # Levanta Supabase local en Docker
supabase db push                  # Aplica migrations pendientes
supabase db reset                 # Resetea y re-aplica todo (dev only)

# Nueva migration
supabase migration new nombre_descriptivo
# Editar el archivo generado en supabase/migrations/
supabase db push

# Ver diferencias
supabase db diff
```

Nombrar migrations con prefijo numérico: `001_initial.sql`, `002_hybrid_search.sql`, etc.

---

## Actualizar indexing_jobs desde Python

```python
# Patrón estándar para actualizar progreso
def update_job_progress(supabase, job_id: str, progress: int):
    supabase.table('indexing_jobs').update({
        'progress': progress,
        'status': 'running'
    }).eq('id', job_id).execute()

def complete_job(supabase, job_id: str):
    supabase.table('indexing_jobs').update({
        'progress': 100,
        'status': 'done',
        'completed_at': 'now()'
    }).eq('id', job_id).execute()

def fail_job(supabase, job_id: str, error: str):
    supabase.table('indexing_jobs').update({
        'status': 'failed',
        'error_message': error,
        'completed_at': 'now()'
    }).eq('id', job_id).execute()
```

---

## Errores frecuentes

| Error | Causa | Solución |
|---|---|---|
| `permission denied for table X` | Usando anon key en server function | Usar service role key |
| `new row violates row-level security` | INSERT sin user_id o user_id incorrecto | Verificar que auth.uid() no es null |
| `vector dimension mismatch` | Embedding de dimensión distinta a 1536 | Verificar `output_dimensionality=1536` en embedder |
| `function hybrid_search does not exist` | Migration 002 no aplicada | `supabase db push` |
| `index scan not used` | `ef_search` bajo o tabla pequeña | Normal en dev con pocos datos; en prod con >1000 chunks el índice se activa |
