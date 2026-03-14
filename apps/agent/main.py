import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
        yield 'event: thinking\ndata: {"node": "classifier", "message": "Processing query..."}\n\n'
        yield 'event: token\ndata: {"text": "This is a placeholder response."}\n\n'
        yield "event: done\ndata: {}\n\n"

    return event_generator()
