# Agentic RAG Platform — AGENTS.md
> Documento maestro del proyecto. Léelo completo antes de cualquier tarea.

---

## Qué es este proyecto

Una plataforma de RAG agéntico de propósito general. El usuario conecta fuentes de conocimiento
(archivos locales PDF/MD/TXT y URLs web), hace preguntas en lenguaje natural, y un agente
LangGraph razona sobre qué buscar, recupera contexto relevante, evalúa si es suficiente, y genera
respuestas con citas verificables a las fuentes originales.

**No es un RAG lineal.** El agente tiene ciclos de reflexión: si el contexto recuperado no es
suficiente, reformula la búsqueda antes de responder.

---

## Stack completo

### Frontend / Full-stack
| Pieza | Tecnología | Notas |
|---|---|---|
| Framework | **TanStack Start** (RC) + `@tanstack/react-start` | SSR, streaming, Server Functions (RPC) |
| Routing | **TanStack Router** v1 | File-based routing, type-safe |
| Estado servidor | **TanStack Query** v5 | Queries, mutations, polling de jobs |
| Bundler | **Vite** (incluido en Start) | — |
| Estilos | **Tailwind CSS v4** | Sin config file, import directo |
| Syntax highlight | **Shiki** | Server-side, zero bundle en cliente |
| Forms | **TanStack Form** | Type-safe, headless |
| Runtime server | **Nitro** (incluido en Start) | Adapters: Node / Vercel / Railway |

### Backend agéntico (Python)
| Pieza | Tecnología | Notas |
|---|---|---|
| Framework | **FastAPI** + **uvicorn** | Async nativo |
| Orquestación | **LangGraph** ≥0.2 + **LangChain** | Grafo de agente con ciclos |
| LLM principal | `gemini-3.1-flash-lite-preview` | Google AI Studio API, thinking levels |
| LLM fallback | `deepseek/deepseek-v3` vía **OpenRouter** | Si Gemini rate-limita |
| Embeddings | `gemini-embedding-001` | 1536 dims (MRL), RETRIEVAL_DOCUMENT/QUERY |
| Ingestión PDF | **pypdf** + **pdfplumber** | pdfplumber para tablas, pypdf para texto |
| Ingestión web | **crawl4ai** | Async, respeta robots.txt, extrae MD limpio |
| Chunking código | **tree-sitter** | AST-aware por función/clase |
| Chunking texto | **langchain-text-splitters** | RecursiveCharacterTextSplitter fallback |
| HTTP client | **httpx** | Async |

### Datos
| Pieza | Tecnología | Notas |
|---|---|---|
| Vector DB + Relacional | **Supabase** (pgvector) | Índice HNSW, RLS policies |
| Auth | **Supabase Auth** | Email+password MVP, OAuth después |
| Migraciones | **supabase CLI** (`supabase/migrations/`) | — |

### Infraestructura
| Pieza | Tecnología | Notas |
|---|---|---|
| Monorepo | **pnpm workspaces** | `pnpm-workspace.yaml` en raíz |
| Deploy frontend | **Vercel** (Nitro adapter) o **Railway** | Nitro soporta ambos |
| Deploy agente | **Railway** (Docker) | `apps/agent/Dockerfile` |
| CI/CD | GitHub Actions | Build + type-check en PR |

---

## Estructura de directorios

```
agentic-rag/
├── AGENTS.md                          # Este archivo — leerlo siempre primero
├── pnpm-workspace.yaml                # workspaces: ['apps/*', 'packages/*']
├── package.json                       # Scripts raíz: dev, build, typecheck
├── tsconfig.json                      # Base TS config
│
├── apps/
│   ├── web/                           # TanStack Start app
│   │   ├── app/
│   │   │   ├── routes/                # File-based routing
│   │   │   │   ├── __root.tsx         # Root layout + providers
│   │   │   │   ├── index.tsx          # Landing / login
│   │   │   │   ├── dashboard/
│   │   │   │   │   ├── index.tsx      # Dashboard principal
│   │   │   │   │   ├── collections/
│   │   │   │   │   │   ├── index.tsx  # Lista de colecciones
│   │   │   │   │   │   └── $id.tsx    # Detalle colección
│   │   │   │   │   └── chat/
│   │   │   │   │       ├── index.tsx  # Nueva conversación
│   │   │   │   │       └── $id.tsx    # Conversación existente
│   │   │   ├── server/                # Server Functions (RPC)
│   │   │   │   ├── auth.ts            # createServerFn() para auth
│   │   │   │   ├── collections.ts     # CRUD colecciones
│   │   │   │   ├── ingest.ts          # Trigger ingestión → agente
│   │   │   │   └── chat.ts            # Proxy streaming SSE → agente
│   │   │   ├── components/
│   │   │   │   ├── chat/
│   │   │   │   │   ├── ChatInput.tsx
│   │   │   │   │   ├── MessageBubble.tsx
│   │   │   │   │   ├── SourcesPanel.tsx
│   │   │   │   │   └── StreamingIndicator.tsx
│   │   │   │   ├── collections/
│   │   │   │   └── ui/                # Componentes base reutilizables
│   │   │   ├── hooks/
│   │   │   │   ├── useChat.ts         # Hook streaming SSE + estado chat
│   │   │   │   └── useIngest.ts       # Hook polling jobs de indexación
│   │   │   ├── lib/
│   │   │   │   ├── supabase.ts        # Cliente Supabase (browser)
│   │   │   │   └── supabase.server.ts # Cliente Supabase (server, service role)
│   │   │   └── router.tsx             # createRouter() entry
│   │   ├── app.config.ts              # TanStack Start config (Vite + Nitro)
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── agent/                         # FastAPI + LangGraph (Python)
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── state.py               # AgentState TypedDict
│       │   ├── graph.py               # StateGraph assembly + compile
│       │   ├── nodes/
│       │   │   ├── classifier.py      # Nodo 1: intent + thinking level
│       │   │   ├── decomposer.py      # Nodo 2: sub-queries
│       │   │   ├── retriever.py       # Nodo 3: hybrid_search() paralelo
│       │   │   ├── evaluator.py       # Edge condicional: ¿suficiente?
│       │   │   ├── ranker.py          # Nodo 4: rerank + dedup
│       │   │   ├── generator.py       # Nodo 5: streaming + fallback
│       │   │   └── formatter.py       # Nodo 6: insertar citas
│       │   └── memory.py              # ConversationSummaryMemory
│       ├── connectors/
│       │   ├── base.py                # BaseConnector ABC
│       │   ├── local_files.py         # PDF, MD, TXT, código
│       │   └── web_crawler.py         # crawl4ai → markdown limpio
│       ├── ingestion/
│       │   ├── chunker.py             # Estrategias por tipo de archivo
│       │   ├── embedder.py            # Batching + retry gemini-embedding-001
│       │   └── pipeline.py            # Orquesta conector→chunk→embed→store
│       ├── db/
│       │   └── supabase.py            # Cliente Supabase Python (service role)
│       ├── main.py                    # FastAPI app: /ingest, /chat/stream, /health
│       ├── Dockerfile
│       ├── requirements.txt
│       └── pyproject.toml
│
├── packages/
│   └── types/                         # Tipos TypeScript compartidos
│       ├── src/
│       │   ├── collections.ts         # Collection, Chunk, IndexingJob
│       │   ├── chat.ts                # Message, Conversation, SSEEvent
│       │   └── index.ts
│       ├── package.json
│       └── tsconfig.json
│
└── supabase/
    ├── config.toml
    └── migrations/
        ├── 001_initial.sql            # Tablas base + pgvector
        ├── 002_hybrid_search.sql      # Función hybrid_search() SQL
        └── 003_rls_policies.sql       # Row Level Security
```

---

## Variables de entorno

### `apps/web/.env.local`
```bash
# Supabase
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...         # Solo server-side, nunca exponer al cliente

# Agente Python
AGENT_URL=http://localhost:8000          # En prod: URL de Railway

# App
VITE_APP_URL=http://localhost:3000
```

### `apps/agent/.env`
```bash
# Google AI Studio
GEMINI_API_KEY=

# Supabase (service role para escritura)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# OpenRouter (fallback LLM)
OPENROUTER_API_KEY=sk-or-...

# Config
PORT=8000
MAX_RETRIEVAL_ITERATIONS=2
DEFAULT_CHUNK_SIZE=800
EMBEDDING_BATCH_SIZE=20
EMBEDDING_DIMENSIONS=1536
```

---

## Schema de Supabase

### Tablas principales

**`collections`** — Espacios de conocimiento del usuario
- `id` UUID PK, `user_id` FK auth.users, `name`, `description`, `status` (ready|indexing|error), `chunk_count`, `created_at`

**`sources`** — Fuentes individuales dentro de una colección
- `id` UUID PK, `collection_id` FK, `type` (file|url), `name`, `original_path`, `url`, `file_size`, `status`, `indexed_at`

**`chunks`** — Fragmentos con embeddings
- `id` UUID PK, `source_id` FK, `collection_id` FK, `content` TEXT, `embedding` vector(1536), `search_vec` tsvector, `metadata` JSONB (file_path, start_line, end_line, url, heading, etc.), `created_at`

**`indexing_jobs`** — Cola de trabajos asíncronos
- `id` UUID PK, `collection_id` FK, `source_id` FK nullable, `status` (queued|running|done|failed), `progress` INT 0-100, `error_message`, `started_at`, `completed_at`

**`conversations`** — Historial de chat
- `id` UUID PK, `user_id` FK, `collection_ids` UUID[], `title`, `summary` TEXT (para memoria comprimida), `created_at`, `updated_at`

**`messages`** — Mensajes individuales
- `id` UUID PK, `conversation_id` FK, `role` (user|assistant), `content` TEXT, `sources` JSONB, `created_at`

### Índices críticos
```sql
-- Búsqueda vectorial (cosine distance)
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Full-text search
CREATE INDEX ON chunks USING gin(search_vec);

-- Filtrado por colección + tipo de archivo
CREATE INDEX ON chunks ((metadata->>'file_ext'));
CREATE INDEX ON chunks (collection_id);
```

### Función hybrid_search
Debe existir como función SQL en Supabase. Recibe:
- `query_embedding vector(1536)` — embedding de la query del usuario
- `query_text text` — texto original para BM25
- `collection_ids uuid[]` — filtro por colecciones
- `match_count int DEFAULT 10`

Retorna chunks fusionados con Reciprocal Rank Fusion:
`rrf_score = 1.0/(rank_dense + 60) + 1.0/(rank_fts + 60)`

---

## Grafo agéntico — resumen de nodos

```
Query usuario
    │
    ▼
[1] Intent Classifier          thinking=low   → intent_type, complexity, thinking_level
    │
    ▼
[2] Query Decomposer           thinking=low   → sub_queries[] (1-4)
    │
    ▼
[3] Parallel Retriever         (no LLM)       → chunks[] via hybrid_search()
    │
    ▼
[edge] Sufficiency Evaluator   thinking=low   → sufficient: bool
    │                                           Si NO y iter<2: reformula → vuelve a [3]
    │                                           Si NO y iter≥2: forzar true
    ▼
[4] Context Ranker             (no LLM)       → top-8 chunks deduplicados
    │
    ▼
[5] Response Generator         thinking=adaptativo  → respuesta raw con [CITE:chunk_id]
    │                           Fallback: OpenRouter si Gemini rate-limita
    ▼
[6] Citation Formatter         (no LLM)       → respuesta final + cited_chunks validados
```

**Regla crítica de citas:** El formatter valida que cada `[CITE:id]` exista en `retrieved_chunks`.
Citas inventadas se eliminan silenciosamente. Nunca incluir citas que no estén en el contexto.

---

## Server Functions vs API Routes

En TanStack Start se usan `createServerFn()` (no API Routes de Next.js).

```typescript
// apps/web/app/server/collections.ts
import { createServerFn } from '@tanstack/react-start'

export const getCollections = createServerFn({ method: 'GET' })
  .handler(async () => {
    // Aquí corre en el servidor — acceso a SUPABASE_SERVICE_ROLE_KEY
    const supabase = createServerSupabaseClient()
    const { data } = await supabase.from('collections').select('*')
    return data
  })
```

Para el streaming del agente, usar un **API handler** de Nitro (no Server Function) porque
las Server Functions no soportan streaming SSE nativo:

```typescript
// apps/web/app/routes/api/chat/stream.ts
import { createAPIFileRoute } from '@tanstack/react-start/api'

export const Route = createAPIFileRoute('/api/chat/stream')({
  POST: async ({ request }) => {
    // Proxy al servicio Python con streaming pass-through
    const upstream = await fetch(`${process.env.AGENT_URL}/chat/stream`, {
      method: 'POST',
      body: request.body,
      headers: { 'Content-Type': 'application/json' },
    })
    return new Response(upstream.body, {
      headers: { 'Content-Type': 'text/event-stream' }
    })
  }
})
```

---

## Eventos SSE del agente

El endpoint `/chat/stream` emite estos eventos en orden:

```
event: thinking
data: {"node": "classifier", "message": "Clasificando pregunta..."}

event: thinking
data: {"node": "retriever", "message": "Buscando en 2 colecciones..."}

event: thinking
data: {"node": "evaluator", "message": "Evaluando contexto recuperado..."}

event: token
data: {"text": "La autenticación en"}

event: token
data: {"text": " este proyecto..."}

event: sources
data: {"chunks": [{"id": "...", "content": "...", "metadata": {...}}]}

event: done
data: {}
```

El hook `useChat.ts` en el frontend parsea estos eventos y actualiza el estado React.

---

## Chunking por tipo de archivo

| Tipo | Estrategia | Chunk size | Overlap | Herramienta |
|---|---|---|---|---|
| `.py` `.ts` `.js` `.go` | AST — por función/clase | 400-1800 tok | 100 tok header | tree-sitter |
| `.md` `.mdx` `.rst` | Por heading `##` | 500 tok | 50 tok | langchain splitter |
| `.pdf` | Por párrafo + sección | 600 tok | 150 tok | pdfplumber |
| `.txt` | RecursiveChar | 800 tok | 200 tok | langchain splitter |
| URL web | Por sección semántica | 500 tok | 50 tok | crawl4ai → md |
| `.json` `.yaml` `.toml` | Documento completo | ≤1800 tok | — | directo |

**Límite duro:** `gemini-embedding-001` acepta máx. **2048 tokens por chunk**.
Diseñar todos los chunks para quedar bajo 1800 tokens con margen.

Siempre preservar `start_line` y `end_line` del archivo original en `metadata`.

---

## Decisiones de arquitectura tomadas (no cambiar sin actualizar este doc)

1. **pnpm workspaces** — No npm, no yarn. Usar `pnpm` para todo.
2. **TanStack Start** para el frontend — No Next.js. Server Functions con `createServerFn()`.
3. **Nitro** como runtime server — Soporta Vercel y Railway sin cambios de código.
4. **Python separado para el agente** — LangGraph no tiene port estable en TS. FastAPI en `apps/agent/`.
5. **Supabase** para todo el storage — pgvector + relacional + auth en un solo lugar.
6. **1536 dimensiones MRL** — No 3072. Misma calidad, mitad de storage, mejor latencia HNSW.
7. **Hybrid search como default** — Dense + BM25 + RRF siempre. No solo vectorial.
8. **Streaming SSE pass-through** — El frontend se conecta al API handler de Nitro que hace proxy al agente Python. No WebSockets.
9. **Ingestión asíncrona** — Nunca bloquear al usuario. Jobs en tabla `indexing_jobs` con polling.
10. **`SUPABASE_SERVICE_ROLE_KEY` solo en servidor** — Nunca en variables `VITE_*` ni en el cliente.

---

## Orden de implementación

```
FASE 1 — Fundación (empezar aquí)
  ├── supabase/migrations/001_initial.sql     ← Tablas + pgvector + HNSW
  ├── supabase/migrations/002_hybrid_search.sql ← Función SQL
  ├── supabase/migrations/003_rls_policies.sql  ← RLS
  ├── apps/web/ scaffold TanStack Start       ← npx @tanstack/start-cli@latest
  ├── apps/web/app/lib/supabase.ts            ← Cliente browser
  ├── apps/web/app/lib/supabase.server.ts     ← Cliente server (service role)
  └── Auth básica (Supabase email+password)

FASE 2 — Ingestión
  ├── apps/agent/ scaffold FastAPI            ← estructura base
  ├── apps/agent/connectors/local_files.py   ← PDF + MD + TXT
  ├── apps/agent/connectors/web_crawler.py   ← crawl4ai
  ├── apps/agent/ingestion/chunker.py
  ├── apps/agent/ingestion/embedder.py       ← gemini-embedding-001
  ├── apps/agent/ingestion/pipeline.py
  ├── apps/agent/main.py POST /ingest
  └── apps/web server function → trigger ingest + polling UI

FASE 3 — Agente LangGraph
  ├── apps/agent/agent/state.py
  ├── apps/agent/agent/nodes/ (todos los nodos)
  ├── apps/agent/agent/graph.py
  ├── apps/agent/main.py POST /chat/stream (SSE)
  └── apps/web/app/routes/api/chat/stream.ts (proxy Nitro)

FASE 4 — Chat UI
  ├── apps/web/app/hooks/useChat.ts           ← SSE parser + estado
  ├── apps/web/app/components/chat/
  └── apps/web/app/routes/dashboard/chat/

FASE 5 — Memoria, pulido y deploy
  ├── apps/agent/agent/memory.py
  ├── Dockerfile para apps/agent/
  └── Deploy Railway (agente) + Vercel (web)
```

---

## Comandos de desarrollo

```bash
# Instalar todo desde raíz
pnpm install

# Dev (ambos servicios)
pnpm dev                    # Inicia web en :3000
cd apps/agent && uvicorn main:app --reload --port 8000

# Solo frontend
pnpm --filter web dev

# Type check
pnpm typecheck

# Supabase local
supabase start
supabase db push            # Aplica migrations

# Tests del agente
cd apps/agent && pytest
```

---

## Límites y consideraciones operativas

- **Rate limit Gemini free tier:** Implementar retry con backoff exponencial en `embedder.py`
  y `generator.py`. Fallback a OpenRouter si `ResourceExhausted`.
- **Timeout Nitro/Vercel:** Las Server Functions tienen límite de 10-25s según plan.
  El streaming SSE evita este problema enviando el primer token antes del límite.
- **RLS obligatorio:** Activar antes de insertar datos de producción. Ver migration 003.
- **Re-indexación:** En MVP, borrar chunks del source y re-indexar completo.
  Re-indexación incremental (por hash de contenido) es trabajo futuro.
- **crawl4ai y robots.txt:** El conector web siempre respetar `robots.txt`.
  No crawlear más de 50 páginas por fuente en MVP.
