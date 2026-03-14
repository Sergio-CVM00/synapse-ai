# SKILL: TanStack Start en este proyecto

> Consultar antes de cualquier tarea que toque el frontend, routing, Server Functions o API handlers.
> TanStack Start está en RC — los patrones aquí son los correctos para este proyecto.

---

## Patrones fundamentales

### Server Functions (datos, mutations)
Para queries y mutations que necesitan acceso al servidor (Supabase service role, variables de entorno).

```typescript
// apps/web/app/server/collections.ts
import { createServerFn } from '@tanstack/react-start'
import { createServerSupabaseClient } from '~/lib/supabase.server'

export const listCollections = createServerFn({ method: 'GET' })
  .handler(async () => {
    const supabase = createServerSupabaseClient()
    const { data, error } = await supabase
      .from('collections')
      .select('*')
      .order('created_at', { ascending: false })
    if (error) throw error
    return data
  })

export const createCollection = createServerFn({ method: 'POST' })
  .validator((data: { name: string; description?: string }) => data)
  .handler(async ({ data }) => {
    const supabase = createServerSupabaseClient()
    const { data: collection, error } = await supabase
      .from('collections')
      .insert(data)
      .select()
      .single()
    if (error) throw error
    return collection
  })
```

Llamar desde componentes:
```typescript
// En un route loader (server-side)
export const Route = createFileRoute('/dashboard/collections/')({
  loader: () => listCollections(),
  component: CollectionsPage,
})

// En un componente con TanStack Query (client-side)
const { data } = useQuery({
  queryKey: ['collections'],
  queryFn: () => listCollections(),
})

// Mutation
const mutation = useMutation({
  mutationFn: createCollection,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] })
})
```

### API Handlers (streaming SSE)
Las Server Functions no soportan streaming. Para SSE usar API handlers de Nitro:

```typescript
// apps/web/app/routes/api/chat/stream.ts
import { createAPIFileRoute } from '@tanstack/react-start/api'

export const Route = createAPIFileRoute('/api/chat/stream')({
  POST: async ({ request }) => {
    const body = await request.json()

    // Proxy al agente Python con streaming pass-through
    const upstream = await fetch(`${process.env.AGENT_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!upstream.ok) {
      return new Response('Agent error', { status: 502 })
    }

    return new Response(upstream.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    })
  },
})
```

---

## File-based routing — convenciones

```
app/routes/
├── __root.tsx              # Layout raíz: providers, nav global
├── index.tsx               # Ruta "/"
├── dashboard/
│   ├── index.tsx           # Ruta "/dashboard"
│   ├── collections/
│   │   ├── index.tsx       # "/dashboard/collections"
│   │   └── $id.tsx         # "/dashboard/collections/:id"
│   └── chat/
│       ├── index.tsx       # "/dashboard/chat" (nueva conversación)
│       └── $id.tsx         # "/dashboard/chat/:id"
└── api/
    └── chat/
        └── stream.ts       # API handler "/api/chat/stream"
```

Estructura mínima de una ruta:
```typescript
// app/routes/dashboard/collections/index.tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/dashboard/collections/')({
  loader: async () => {
    return await listCollections()   // Server Function
  },
  component: CollectionsPage,
})

function CollectionsPage() {
  const collections = Route.useLoaderData()
  // ...
}
```

---

## TanStack Query — patrones para este proyecto

```typescript
// Polling de indexing jobs (actualiza cada 2s mientras status !== done|failed)
const { data: job } = useQuery({
  queryKey: ['indexing-job', jobId],
  queryFn: () => getIndexingJob({ data: { jobId } }),
  refetchInterval: (query) => {
    const status = query.state.data?.status
    if (status === 'done' || status === 'failed') return false
    return 2000
  },
})

// Invalidar colecciones cuando un job termina
useEffect(() => {
  if (job?.status === 'done') {
    queryClient.invalidateQueries({ queryKey: ['collections'] })
  }
}, [job?.status])
```

---

## Supabase Auth en TanStack Start

```typescript
// app/lib/supabase.ts — cliente browser
import { createBrowserClient } from '@supabase/ssr'

export const supabase = createBrowserClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

// app/lib/supabase.server.ts — cliente servidor (solo en Server Functions)
import { createServerClient } from '@supabase/ssr'

export function createServerSupabaseClient() {
  return createServerClient(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { cookies: { getAll: () => [], setAll: () => {} } }
  )
}
```

Proteger rutas con `beforeLoad`:
```typescript
export const Route = createFileRoute('/dashboard')({
  beforeLoad: async () => {
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) throw redirect({ to: '/' })
  },
})
```

---

## app.config.ts — configuración estándar del proyecto

```typescript
// apps/web/app.config.ts
import { defineConfig } from '@tanstack/react-start/config'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  server: {
    preset: 'node-server',   // Cambiar a 'vercel' para deploy en Vercel
  },
  vite: {
    plugins: [tailwindcss()],
  },
  routers: {
    client: {
      entry: './app/client.tsx',
    },
    server: {
      entry: './app/server.tsx',
    },
    ssr: {
      entry: './app/ssr.tsx',
    },
  },
})
```

---

## Errores frecuentes en TanStack Start RC

| Error | Causa | Solución |
|---|---|---|
| `createServerFn` no disponible | Import incorrecto | `import { createServerFn } from '@tanstack/react-start'` |
| Variables de entorno `undefined` en cliente | Usando `process.env` en código cliente | Variables del cliente deben ser `VITE_*` y accederse con `import.meta.env` |
| Streaming no funciona | Usando Server Function para SSE | Usar API handler con `createAPIFileRoute` |
| Route no encontrada | Archivo mal nombrado | Verificar convención: `$param.tsx` para params dinámicos, `index.tsx` para raíz |
| Hydration mismatch | Server y cliente renderizan distinto | Verificar que loaders retornan datos deterministas |
