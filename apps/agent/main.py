import uuid
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.graph import run_agent_async

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    collection_id: str
    source_type: str
    source_path: str


class ChatRequest(BaseModel):
    query: str
    collection_ids: list[str]
    conversation_id: str | None = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(request: IngestRequest):
    job_id = str(uuid.uuid4())
    return {"job_id": job_id}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        # Yield initial thinking event
        yield 'event: thinking\ndata: {"node": "classifier", "message": "Processing query..."}\n\n'

        try:
            # Run the agent
            result = await run_agent_async(
                query=request.query,
                collection_ids=request.collection_ids,
                conversation_id=request.conversation_id,
            )

            # Yield thinking events for each stage
            yield 'event: thinking\ndata: {"node": "decomposer", "message": "Decomposing query..."}\n\n'
            yield 'event: thinking\ndata: {"node": "retriever", "message": "Retrieving relevant context..."}\n\n'
            yield 'event: thinking\ndata: {"node": "evaluator", "message": "Evaluating context sufficiency..."}\n\n'
            yield 'event: thinking\ndata: {"node": "ranker", "message": "Ranking and deduplicating results..."}\n\n'
            yield 'event: thinking\ndata: {"node": "generator", "message": "Generating response..."}\n\n'

            # Stream the response as tokens (chunk into smaller pieces)
            response = result.get("response", "")
            chunk_size = 20
            for i in range(0, len(response), chunk_size):
                chunk = response[i : i + chunk_size]
                yield f'event: token\ndata: {{"text": {json.dumps(chunk)}}}\n\n'

            # Yield sources
            cited_chunks = result.get("cited_chunks", [])
            chunks_data = [
                {
                    "id": chunk.get("id"),
                    "content": chunk.get("content", "")[:200],  # Truncate for transport
                    "metadata": chunk.get("metadata", {}),
                }
                for chunk in cited_chunks
            ]
            yield f'event: sources\ndata: {{"chunks": {json.dumps(chunks_data)}}}\n\n'

        except Exception as e:
            yield f'event: error\ndata: {{"message": {json.dumps(str(e))}}}\n\n'

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
