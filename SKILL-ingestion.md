# SKILL: Pipeline de Ingestión en este proyecto

> Consultar antes de cualquier tarea en `apps/agent/connectors/` o `apps/agent/ingestion/`.

---

## Conector de archivos locales

```python
# apps/agent/connectors/local_files.py
import pdfplumber
import pypdf
from pathlib import Path
from .base import BaseConnector, DocumentContent

SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.mdx', '.txt', '.rst', '.py',
                         '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml',
                         '.yml', '.toml', '.env.example'}

class LocalFilesConnector(BaseConnector):
    def __init__(self, file_paths: list[str]):
        self.paths = [Path(p) for p in file_paths]

    async def fetch_content(self, path: Path) -> DocumentContent:
        ext = path.suffix.lower()

        if ext == '.pdf':
            return self._extract_pdf(path)
        else:
            text = path.read_text(encoding='utf-8', errors='replace')
            return DocumentContent(text=text, ext=ext, name=path.name)

    def _extract_pdf(self, path: Path) -> DocumentContent:
        # Intentar pdfplumber primero (mejor para tablas y texto estructurado)
        try:
            with pdfplumber.open(path) as pdf:
                pages = []
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ''
                    if text.strip():
                        pages.append(f'[Página {i+1}]\n{text}')
                return DocumentContent(
                    text='\n\n'.join(pages),
                    ext='.pdf',
                    name=path.name,
                )
        except Exception:
            # Fallback a pypdf
            reader = pypdf.PdfReader(str(path))
            text = '\n\n'.join(
                f'[Página {i+1}]\n{page.extract_text()}'
                for i, page in enumerate(reader.pages)
                if page.extract_text()
            )
            return DocumentContent(text=text, ext='.pdf', name=path.name)
```

## Conector web (crawl4ai)

```python
# apps/agent/connectors/web_crawler.py
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

MAX_PAGES_PER_SOURCE = 50   # Límite MVP

class WebCrawlerConnector(BaseConnector):
    async def fetch_url(self, url: str) -> DocumentContent:
        config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.ENABLED,       # Cache para no re-crawlear en dev
            word_count_threshold=50,             # Ignorar páginas con poco contenido
            excluded_tags=['nav', 'footer', 'header', 'aside', 'script', 'style'],
            remove_overlay_elements=True,
            # Respeta robots.txt automáticamente
        )

        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            raise ValueError(f'No se pudo crawlear {url}: {result.error_message}')

        # crawl4ai retorna markdown limpio en result.markdown
        return DocumentContent(
            text=result.markdown,
            ext='.md',          # Tratar como markdown para chunking
            name=url,
            url=url,
            title=result.metadata.get('title', ''),
        )

    async def crawl_site(self, start_url: str, max_pages: int = MAX_PAGES_PER_SOURCE):
        """Crawl recursivo hasta max_pages páginas del mismo dominio."""
        config = CrawlerRunConfig(
            deep_crawl_strategy=BFSDeepCrawlStrategy(
                max_depth=2,
                max_pages=max_pages,
                filter_links=True,    # Solo links del mismo dominio
            )
        )
        async with AsyncWebCrawler() as crawler:
            results = await crawler.arun(url=start_url, config=config)
        return results   # list de resultados
```

---

## Chunker — estrategia por extensión

```python
# apps/agent/ingestion/chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dataclasses import dataclass

MAX_CHUNK_TOKENS = 1800   # Margen bajo el límite de 2048 del embedder

@dataclass
class Chunk:
    text: str
    start_line: int
    end_line: int
    file_ext: str
    file_path: str | None = None
    url: str | None = None
    heading: str | None = None  # Para chunks de MD/web

def chunk_document(content: str, ext: str, source_path: str) -> list[Chunk]:
    ext = ext.lower()

    if ext in {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java'}:
        return chunk_code_ast(content, ext, source_path)

    elif ext in {'.md', '.mdx', '.rst'}:
        return chunk_markdown(content, source_path)

    elif ext == '.pdf':
        return chunk_pdf_text(content, source_path)

    elif ext in {'.json', '.yaml', '.yml', '.toml', '.env.example'}:
        # Documento completo si no supera el límite
        tokens = estimate_tokens(content)
        if tokens <= MAX_CHUNK_TOKENS:
            lines = content.splitlines()
            return [Chunk(text=content, start_line=1, end_line=len(lines),
                          file_ext=ext, file_path=source_path)]
        else:
            # Truncar con nota
            truncated = content[:MAX_CHUNK_TOKENS * 4] + '\n... [truncado]'
            return [Chunk(text=truncated, start_line=1,
                          end_line=MAX_CHUNK_TOKENS * 4 // 60,
                          file_ext=ext, file_path=source_path)]

    else:
        # Fallback: RecursiveCharacterTextSplitter
        return chunk_text_fallback(content, ext, source_path)


def chunk_markdown(content: str, source_path: str) -> list[Chunk]:
    """Divide por secciones ## preservando el heading."""
    chunks = []
    sections = re.split(r'\n(#{1,3} .+)\n', content)
    current_heading = ''
    current_text = ''
    start_line = 1

    for part in sections:
        if re.match(r'^#{1,3} ', part):
            if current_text.strip():
                lines = current_text.splitlines()
                if estimate_tokens(current_text) <= MAX_CHUNK_TOKENS:
                    chunks.append(Chunk(
                        text=f'{current_heading}\n{current_text}'.strip(),
                        start_line=start_line,
                        end_line=start_line + len(lines),
                        file_ext='.md',
                        file_path=source_path,
                        heading=current_heading,
                    ))
            current_heading = part
            start_line += len(current_text.splitlines()) + 1
            current_text = ''
        else:
            current_text += part

    # Último chunk
    if current_text.strip():
        chunks.append(Chunk(
            text=f'{current_heading}\n{current_text}'.strip(),
            start_line=start_line,
            end_line=start_line + len(current_text.splitlines()),
            file_ext='.md',
            file_path=source_path,
            heading=current_heading,
        ))
    return chunks


def chunk_text_fallback(content: str, ext: str, source_path: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800 * 4,    # Aprox tokens → chars (1 token ≈ 4 chars)
        chunk_overlap=200 * 4,
        length_function=len,
    )
    texts = splitter.split_text(content)
    lines = content.splitlines()
    chunks = []
    line_cursor = 0

    for text in texts:
        text_lines = text.splitlines()
        chunks.append(Chunk(
            text=text,
            start_line=line_cursor + 1,
            end_line=line_cursor + len(text_lines),
            file_ext=ext,
            file_path=source_path,
        ))
        line_cursor += len(text_lines)

    return chunks


def estimate_tokens(text: str) -> int:
    """Estimación rápida: 1 token ≈ 4 caracteres en inglés/español."""
    return len(text) // 4
```

---

## Pipeline de ingestión completo

```python
# apps/agent/ingestion/pipeline.py
async def ingest_source(
    source_id: str,
    collection_id: str,
    connector,            # BaseConnector instance
    job_id: str,
    supabase,
):
    try:
        # 1. Obtener contenido
        update_job_progress(supabase, job_id, 10)
        documents = await connector.fetch_all()

        # 2. Chunking
        update_job_progress(supabase, job_id, 30)
        all_chunks = []
        for doc in documents:
            chunks = chunk_document(doc.text, doc.ext, doc.name)
            all_chunks.extend(chunks)

        # 3. Embeddings en batches
        update_job_progress(supabase, job_id, 50)
        texts = [c.text for c in all_chunks]
        embeddings = await embed_all_chunks(texts)

        # 4. Insertar en Supabase
        update_job_progress(supabase, job_id, 80)
        rows = [
            {
                'source_id': source_id,
                'collection_id': collection_id,
                'content': chunk.text,
                'embedding': embedding,
                'metadata': {
                    'file_path': chunk.file_path,
                    'url': chunk.url,
                    'start_line': chunk.start_line,
                    'end_line': chunk.end_line,
                    'file_ext': chunk.file_ext,
                    'heading': chunk.heading,
                }
            }
            for chunk, embedding in zip(all_chunks, embeddings)
        ]

        # Insertar en batches de 100
        for i in range(0, len(rows), 100):
            supabase.table('chunks').insert(rows[i:i+100]).execute()

        # 5. Actualizar estados
        supabase.table('sources').update({
            'status': 'indexed',
            'indexed_at': 'now()',
        }).eq('id', source_id).execute()

        complete_job(supabase, job_id)

    except Exception as e:
        fail_job(supabase, job_id, str(e))
        raise
```

---

## Endpoint de ingestión en FastAPI

```python
# apps/agent/main.py
class IngestRequest(BaseModel):
    source_id: str
    collection_id: str
    job_id: str
    type: str              # 'file' | 'url'
    # Para archivos:
    file_content: str | None = None   # Base64 o texto
    file_name: str | None = None
    file_ext: str | None = None
    # Para URLs:
    url: str | None = None
    crawl_depth: int = 1

@app.post('/ingest')
async def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """
    Retorna inmediatamente con job_id.
    La ingestión corre en background.
    """
    if req.type == 'url':
        connector = WebCrawlerConnector(req.url, req.crawl_depth)
    else:
        connector = LocalFilesConnector(...)

    background_tasks.add_task(
        ingest_source,
        source_id=req.source_id,
        collection_id=req.collection_id,
        connector=connector,
        job_id=req.job_id,
        supabase=get_supabase_client(),
    )

    return {'job_id': req.job_id, 'status': 'queued'}
```

---

## Límites y edge cases

| Situación | Comportamiento esperado |
|---|---|
| PDF escaneado (solo imágenes) | pdfplumber extrae nada; pypdf también falla → loggear warning, marcar source con error |
| URL devuelve 403/404 | crawl4ai lo reporta en `result.success=False` → propagar como error del job |
| Archivo > 50MB | Rechazar en el upload del frontend antes de llamar al agente |
| Chunk estimado > 1800 tokens | RecursiveCharacterTextSplitter subdivide automáticamente |
| Website con JS dinámico | crawl4ai usa Playwright → funciona; puede ser lento (5-10s por página) |
| Sitio sin robots.txt | crawl4ai asume permitido; igualmente limitar a 50 páginas |
