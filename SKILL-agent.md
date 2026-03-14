# SKILL: Agente LangGraph + Gemini en este proyecto

> Consultar antes de cualquier tarea en `apps/agent/`.

---

## Cliente Gemini — configuración correcta

```python
# apps/agent/agent/nodes/generator.py y classifier.py
from google import genai

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

# Generar texto (con thinking level)
response = client.models.generate_content(
    model='gemini-3.1-flash-lite-preview',
    contents=prompt,
    config={
        'thinking_level': 'low',      # 'low' | 'medium' | 'high'
        'max_output_tokens': 500,
        'temperature': 0.1,           # Bajo para clasificación/análisis
    }
)
text = response.text

# Streaming
for chunk in client.models.generate_content_stream(
    model='gemini-3.1-flash-lite-preview',
    contents=prompt,
    config={'thinking_level': 'medium', 'max_output_tokens': 1500},
):
    if chunk.text:
        yield chunk.text
```

## Embeddings — configuración correcta

```python
# apps/agent/ingestion/embedder.py
from google import genai

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

# Para chunks (al indexar)
result = client.models.embed_content(
    model='gemini-embedding-001',
    contents=chunk_text,
    config={
        'task_type': 'RETRIEVAL_DOCUMENT',
        'output_dimensionality': 1536,   # MRL — nunca cambiar esto
    }
)
embedding = result.embeddings[0].values  # list[float] de 1536

# Para queries (al buscar)
result = client.models.embed_content(
    model='gemini-embedding-001',
    contents=user_query,
    config={
        'task_type': 'RETRIEVAL_QUERY',
        'output_dimensionality': 1536,
    }
)
```

## Batching con retry — patrón obligatorio

```python
# apps/agent/ingestion/embedder.py
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BATCH_SIZE = int(os.environ.get('EMBEDDING_BATCH_SIZE', '20'))

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def embed_batch(texts: list[str], task_type: str = 'RETRIEVAL_DOCUMENT') -> list[list[float]]:
    """Embeddea un batch de textos con retry automático."""
    embeddings = []
    for text in texts:
        result = client.models.embed_content(
            model='gemini-embedding-001',
            contents=text,
            config={'task_type': task_type, 'output_dimensionality': 1536},
        )
        embeddings.append(result.embeddings[0].values)
    return embeddings

async def embed_all_chunks(chunks: list[str]) -> list[list[float]]:
    all_embeddings = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_embeddings = await embed_batch(batch)
        all_embeddings.extend(batch_embeddings)
        await asyncio.sleep(0.5)   # Pequeña pausa entre batches
    return all_embeddings
```

## Fallback a OpenRouter

```python
# apps/agent/agent/nodes/generator.py
import httpx

OPENROUTER_MODEL = 'deepseek/deepseek-v3'

async def call_llm_with_fallback(prompt: str, thinking_level: str) -> AsyncIterator[str]:
    try:
        async for token in call_gemini_streaming(prompt, thinking_level):
            yield token
    except Exception as e:
        if 'ResourceExhausted' in str(e) or '429' in str(e):
            async for token in call_openrouter_streaming(prompt):
                yield token
        else:
            raise

async def call_openrouter_streaming(prompt: str) -> AsyncIterator[str]:
    async with httpx.AsyncClient() as http:
        async with http.stream(
            'POST',
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {os.environ["OPENROUTER_API_KEY"]}'},
            json={
                'model': OPENROUTER_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith('data: ') and line != 'data: [DONE]':
                    data = json.loads(line[6:])
                    token = data['choices'][0]['delta'].get('content', '')
                    if token:
                        yield token
```

---

## State object del grafo

```python
# apps/agent/agent/state.py
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Input del usuario
    user_query: str
    collection_ids: list[str]
    conversation_history: list[dict]   # [{'role': 'user'|'assistant', 'content': str}]

    # Nodo 1: Classifier
    intent_type: str          # simple_lookup | explanation | cross_source | code_trace | analysis
    complexity: int           # 1-5
    thinking_level: str       # low | medium | high

    # Nodo 2: Decomposer
    sub_queries: list[str]    # Default: [user_query]

    # Nodo 3: Retriever
    retrieved_chunks: list[dict]
    retrieval_iterations: int  # Contador anti-loop (máx 2)

    # Edge: Evaluator
    context_sufficient: bool
    confidence_score: float
    reformulated_queries: list[str]   # Si no es suficiente

    # Nodo 4: Ranker
    ranked_chunks: list[dict]         # Top-8

    # Nodos 5-6: Generator + Formatter
    raw_response: str
    final_response: str
    cited_chunks: list[dict]
```

## Assembly del grafo

```python
# apps/agent/agent/graph.py
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import classifier, decomposer, retriever, ranker, generator, formatter
from .nodes.evaluator import should_continue   # Función edge condicional

def build_graph():
    g = StateGraph(AgentState)

    g.add_node('classifier', classifier.run)
    g.add_node('decomposer', decomposer.run)
    g.add_node('retriever', retriever.run)
    g.add_node('ranker', ranker.run)
    g.add_node('generator', generator.run)
    g.add_node('formatter', formatter.run)

    g.set_entry_point('classifier')
    g.add_edge('classifier', 'decomposer')
    g.add_edge('decomposer', 'retriever')

    # Edge condicional: retry si contexto insuficiente
    g.add_conditional_edges(
        'retriever',
        should_continue,
        {'continue': 'ranker', 'retry': 'retriever'}
    )

    g.add_edge('ranker', 'generator')
    g.add_edge('generator', 'formatter')
    g.add_edge('formatter', END)

    return g.compile()

graph = build_graph()
```

---

## Endpoint SSE en FastAPI

```python
# apps/agent/main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    query: str
    collection_ids: list[str]
    conversation_history: list[dict] = []
    conversation_id: str | None = None

@app.post('/chat/stream')
async def chat_stream(req: ChatRequest):
    async def event_generator():
        state = {
            'user_query': req.query,
            'collection_ids': req.collection_ids,
            'conversation_history': req.conversation_history,
            'retrieval_iterations': 0,
        }

        async for event in graph.astream_events(state, version='v2'):
            kind = event['event']

            # Emitir progreso del nodo
            if kind == 'on_chain_start' and event.get('name') in NODE_MESSAGES:
                msg = NODE_MESSAGES[event['name']]
                yield f"event: thinking\ndata: {json.dumps({'node': event['name'], 'message': msg})}\n\n"

            # Emitir tokens del generator
            if kind == 'on_chat_model_stream':
                token = event['data']['chunk'].content
                if token:
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

        # Emitir fuentes al final
        # (recuperar cited_chunks del estado final del grafo)
        yield f"event: sources\ndata: {json.dumps({'chunks': cited_chunks})}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type='text/event-stream')

NODE_MESSAGES = {
    'classifier': 'Clasificando pregunta...',
    'decomposer': 'Analizando sub-preguntas...',
    'retriever': 'Buscando en las colecciones...',
    'ranker': 'Evaluando contexto recuperado...',
    'generator': 'Generando respuesta...',
    'formatter': 'Verificando citas...',
}
```

---

## Thinking levels — cuándo usar cada uno

| Nodo | Thinking level | Razón |
|---|---|---|
| classifier | `low` | Clasificación simple, no necesita razonamiento profundo |
| decomposer | `low` | Descomponer query, tarea mecánica |
| evaluator | `low` | Evaluación binaria con heurística |
| generator (simple_lookup) | `low` | Pregunta de hecho puntual |
| generator (explanation) | `medium` | Síntesis de varios chunks |
| generator (cross_source/code_trace/analysis) | `high` | Razonamiento complejo |

El `thinking_level` para el generator lo determina el `classifier` en el nodo 1
y se propaga en `AgentState.thinking_level`.

---

## Prompt del generator — estructura obligatoria

```python
SYSTEM_PROMPT = """Eres un asistente experto. Responde ÚNICAMENTE basándote en el contexto provisto.

Para cada afirmación que hagas, cita el fragmento fuente usando: [CITE:chunk_id]
Si la misma afirmación viene de múltiples fuentes: [CITE:id1][CITE:id2]
Si no tienes información suficiente para responder, dilo explícitamente.
No inventes información ni cites IDs que no estén en el contexto.
"""

def build_prompt(query: str, chunks: list[dict], history: list[dict]) -> str:
    context_parts = []
    for chunk in chunks:
        meta = chunk['metadata']
        source_label = meta.get('url') or meta.get('file_path', 'desconocido')
        context_parts.append(
            f"[CHUNK ID: {chunk['id']}]\n"
            f"Fuente: {source_label}\n"
            f"Contenido:\n{chunk['content']}\n"
        )

    history_text = '\n'.join(
        f"{m['role'].upper()}: {m['content']}"
        for m in history[-6:]   # Últimos 6 mensajes
    )

    return (
        f"CONTEXTO DISPONIBLE:\n{'---'.join(context_parts)}\n\n"
        f"HISTORIAL:\n{history_text}\n\n"
        f"PREGUNTA: {query}"
    )
```

---

## Errores frecuentes

| Error | Causa | Solución |
|---|---|---|
| `ResourceExhausted` en Gemini | Rate limit del free tier | Activar fallback a OpenRouter; añadir `await asyncio.sleep(1)` entre requests |
| Citas `[CITE:id]` inventadas | El modelo alucina IDs | El `formatter.py` valida que cada ID exista en `ranked_chunks`; ignorar los inválidos |
| Loop infinito en retriever | `evaluator` nunca devuelve `continue` | Forzar `context_sufficient = True` cuando `retrieval_iterations >= 2` |
| Embedding dimension error | Olvidar `output_dimensionality=1536` | Siempre especificar en toda llamada a `embed_content` |
| Chunks muy grandes | Texto supera 2048 tokens | Verificar en `chunker.py` que ningún chunk supere 1800 tokens antes de embedear |
