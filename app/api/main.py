"""GroundsWell agent API — FastAPI with SSE chat."""
import json
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import agent
import es_tools
from config import ES_URL, MODEL

app = FastAPI(title="GroundsWell API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/health")
def health():
    try:
        ok = es_tools.es.ping()
        n = es_tools.es.count(index="groundswell-zillow_indices")["count"]
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "es": str(e)}
    return {"status": "ok", "es_url": ES_URL, "es_reachable": ok, "model": MODEL, "zillow_docs": n}


@app.get("/metros")
def list_metros():
    return es_tools.metros()


@app.post("/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())[:12]

    def stream():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        try:
            for event in agent.run(session_id, req.message):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
