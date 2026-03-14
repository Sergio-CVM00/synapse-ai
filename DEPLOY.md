# Deploy Guide — Render (Free Tier) + Vercel

> Deploy final del proyecto: agente Python en Render, frontend en Vercel.
> Coste total: $0/mes con uso personal.

---

## Arquitectura de producción

```
Browser
  │
  ▼
Vercel (TanStack Start / Nitro)          — frontend + server functions
  │  AGENT_URL=https://agentic-rag-agent.onrender.com
  ▼
Render (FastAPI + LangGraph)             — agente Python
  │
  ▼
Supabase (pgvector)                      — base de datos
```

---

## Parte 1 — Archivos necesarios en el repo

### 1.1 `apps/agent/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para crawl4ai (Playwright) y pdfplumber
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar browsers de Playwright para crawl4ai
RUN playwright install chromium --with-deps

# Copiar código
COPY . .

# Puerto que expone Render
EXPOSE 8000

# Comando de arranque
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 1.2 `apps/agent/requirements.txt`

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.7.0

# LangGraph + LangChain
langgraph>=0.2.0
langchain>=0.2.0
langchain-google-genai>=1.0.0
langchain-text-splitters>=0.2.0

# Google AI
google-genai>=0.5.0

# Supabase
supabase>=2.4.0

# Ingestión
pypdf>=4.0.0
pdfplumber>=0.11.0
crawl4ai>=0.3.0
tree-sitter>=0.21.0

# HTTP + utils
httpx>=0.27.0
tenacity>=8.3.0
python-dotenv>=1.0.0
```

### 1.3 `apps/agent/render.yaml` (opcional pero recomendado)

Infrastructure as Code para Render. Si existe en el repo, Render lo detecta automáticamente:

```yaml
services:
  - type: web
    name: agentic-rag-agent
    runtime: docker
    rootDir: apps/agent
    dockerfilePath: ./Dockerfile
    plan: free
    healthCheckPath: /health
    envVars:
      - key: GEMINI_API_KEY
        sync: false          # Se configura manualmente en el dashboard
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: OPENROUTER_API_KEY
        sync: false
      - key: MAX_RETRIEVAL_ITERATIONS
        value: "2"
      - key: EMBEDDING_BATCH_SIZE
        value: "20"
      - key: EMBEDDING_DIMENSIONS
        value: "1536"
      - key: PORT
        value: "8000"
```

### 1.4 Endpoint `/health` en `apps/agent/main.py`

Render hace ping a este endpoint para saber si el servicio está vivo.
Sin esto, Render no sabe cuándo el deploy terminó correctamente:

```python
@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 1.5 `app.config.ts` — preset Nitro para Vercel

```typescript
// apps/web/app.config.ts
import { defineConfig } from '@tanstack/react-start/config'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  server: {
    preset: 'vercel',   // Cambiar de 'node-server' a 'vercel'
  },
  vite: {
    plugins: [tailwindcss()],
  },
})
```

### 1.6 `apps/web/vercel.json`

Le dice a Vercel que el root del proyecto es `apps/web` dentro del monorepo
y que use pnpm:

```json
{
  "buildCommand": "pnpm --filter web build",
  "outputDirectory": "apps/web/.output/public",
  "installCommand": "pnpm install",
  "framework": null
}
```

> **Nota:** TanStack Start con Nitro genera el output en `.output/`.
> Si esto cambia en versiones futuras del RC, verificar la carpeta generada
> con `pnpm --filter web build` localmente y ajustar `outputDirectory`.

---

## Parte 2 — Deploy del agente en Render

### Paso 1: Crear cuenta y nuevo servicio

1. Ir a [render.com](https://render.com) → crear cuenta con GitHub
2. Dashboard → **New** → **Web Service**
3. Conectar el repositorio de GitHub del proyecto
4. Render escanea el repo automáticamente

### Paso 2: Configurar el servicio

En la pantalla de configuración:

| Campo | Valor |
|---|---|
| **Name** | `agentic-rag-agent` |
| **Region** | Frankfurt (EU) — más cercano a Sevilla |
| **Branch** | `main` |
| **Root Directory** | `apps/agent` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `./Dockerfile` |
| **Plan** | `Free` |

### Paso 3: Variables de entorno

En la sección **Environment Variables** del servicio, añadir:

```
GEMINI_API_KEY          → tu key de Google AI Studio
SUPABASE_URL            → https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY → eyJ...
OPENROUTER_API_KEY      → sk-or-...
MAX_RETRIEVAL_ITERATIONS → 2
EMBEDDING_BATCH_SIZE    → 20
EMBEDDING_DIMENSIONS    → 1536
PORT                    → 8000
```

### Paso 4: Deploy

Clic en **Create Web Service**. Render empieza a construir la imagen Docker.
El primer build tarda ~5-10 minutos (descarga de dependencias Python + Playwright).

Una vez desplegado, la URL del agente queda en:
```
https://agentic-rag-agent.onrender.com
```

Verificar que funciona:
```bash
curl https://agentic-rag-agent.onrender.com/health
# → {"status": "ok"}
```

---

## Parte 3 — Keep-alive para evitar cold starts

El plan gratuito de Render duerme el servicio tras **15 minutos de inactividad**
y el wake-up tarda ~50 segundos. Para un proyecto personal en uso activo esto
es aceptable, pero si quieres evitarlo completamente:

### Opción A: cron-job.org (gratuito, recomendado)

1. Ir a [cron-job.org](https://cron-job.org) → crear cuenta gratuita
2. **Create cronjob**:
   - URL: `https://agentic-rag-agent.onrender.com/health`
   - Schedule: every **14 minutes**
   - Method: `GET`
3. Guardar

El servicio nunca llega a dormirse porque recibe un ping cada 14 minutos.

### Opción B: GitHub Actions (si prefieres no usar servicios externos)

```yaml
# .github/workflows/keep-alive.yml
name: Keep Render alive

on:
  schedule:
    - cron: '*/14 * * * *'   # Cada 14 minutos

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping agent
        run: curl -f https://agentic-rag-agent.onrender.com/health
```

> **Nota:** GitHub Actions free tier tiene 2000 min/mes.
> Este workflow consume ~3000 min/mes (14 min × ~215 ejecuciones/día × 1 min).
> Supera el límite — usar cron-job.org en su lugar.

---

## Parte 4 — Deploy del frontend en Vercel

### Paso 1: Importar proyecto

1. Ir a [vercel.com](https://vercel.com) → **Add New Project**
2. Importar el repositorio de GitHub
3. Vercel detecta el repo como monorepo

### Paso 2: Configurar el proyecto

| Campo | Valor |
|---|---|
| **Framework Preset** | `Other` (no Next.js, no Vite — es TanStack Start) |
| **Root Directory** | `apps/web` |
| **Build Command** | `pnpm --filter web build` |
| **Output Directory** | `.output/public` |
| **Install Command** | `pnpm install` |

### Paso 3: Variables de entorno en Vercel

En **Settings → Environment Variables**, añadir:

```
VITE_SUPABASE_URL            → https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY       → eyJ...         (público, prefijo VITE_)
SUPABASE_SERVICE_ROLE_KEY    → eyJ...         (secreto, sin prefijo VITE_)
AGENT_URL                    → https://agentic-rag-agent.onrender.com
VITE_APP_URL                 → https://tu-app.vercel.app
```

> `AGENT_URL` **nunca** con prefijo `VITE_` — solo se usa en server-side
> (API handler de Nitro que hace proxy al agente). Si llevara `VITE_`
> se expondría al navegador y cualquiera podría llamar al agente directamente.

### Paso 4: Deploy

Clic en **Deploy**. El primer deploy tarda ~3 minutos.

URL resultante: `https://agentic-rag.vercel.app` (o dominio personalizado).

---

## Parte 5 — Actualizar Supabase Auth

Supabase necesita saber la URL de producción del frontend para redirigir
correctamente después del login.

1. Ir a Supabase Dashboard → **Authentication → URL Configuration**
2. **Site URL**: `https://agentic-rag.vercel.app`
3. **Redirect URLs**: añadir `https://agentic-rag.vercel.app/**`

---

## Parte 6 — Flujo de deploy continuo

Una vez configurado, el ciclo de trabajo es:

```bash
# Desarrollo local
pnpm dev                        # Frontend en :3000
uvicorn main:app --reload       # Agente en :8000

# Subir cambios
git add .
git commit -m "feat: nueva funcionalidad"
git push origin main
# → Render redeploya el agente automáticamente
# → Vercel redeploya el frontend automáticamente
```

Ambos servicios tienen **auto-deploy** activado por defecto al hacer push a `main`.

---

## Resumen de URLs en producción

| Servicio | URL |
|---|---|
| Frontend | `https://agentic-rag.vercel.app` |
| Agente (health check) | `https://agentic-rag-agent.onrender.com/health` |
| Agente (chat stream) | `https://agentic-rag-agent.onrender.com/chat/stream` |
| Agente (ingest) | `https://agentic-rag-agent.onrender.com/ingest` |
| Supabase | `https://xxx.supabase.co` |

---

## Troubleshooting frecuente

| Problema | Causa probable | Solución |
|---|---|---|
| Build falla en Render con error de Playwright | `playwright install` necesita deps del SO | Verificar que el `apt-get` del Dockerfile incluye `wget` |
| `AGENT_URL` no responde desde Vercel | Render durmió el servicio | Activar keep-alive con cron-job.org |
| SSE stream se corta a los 10s en Vercel | Límite de funciones serverless de Vercel free | El preset `vercel` de Nitro usa Edge Runtime que no tiene este límite — verificar que `preset: 'vercel'` está en `app.config.ts` |
| Variables de entorno `undefined` en producción | Añadidas después del último deploy | En Vercel: **Redeploy** después de añadir variables. En Render: el servicio se reinicia automáticamente |
| `permission denied` en Supabase | `SUPABASE_SERVICE_ROLE_KEY` no configurada en Render | Verificar env vars en Render Dashboard → Environment |
| Cold start de 50s en primer request | Render free durmió el servicio | Configurar cron-job.org keep-alive |
