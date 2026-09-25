import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import run_agent
from tools import query_projects
from export import export_to_xlsx

app = FastAPI(title="Supabase Project Agent API")

# Sesuaikan origin dengan domain Next.js kamu
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    reply: str
    tool_results: List[Any] = []


class FilterRequest(BaseModel):
    search: Optional[str] = None
    status: Optional[str] = None
    member_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 200


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Endpoint utama chat agent — dipakai dari FE untuk natural language query."""
    history = [h.model_dump() for h in (req.history or [])]
    try:
        result = run_agent(req.message, history)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/projects/filter")
def filter_projects(req: FilterRequest) -> List[Dict[str, Any]]:
    """
    Endpoint langsung untuk UI filter (search project, status, member, tanggal)
    tanpa lewat LLM — dipakai FE untuk tabel/list yang cepat & deterministik.
    """
    return query_projects.invoke(req.model_dump())


@app.post("/projects/export")
def export_projects(req: FilterRequest):
    """Filter data lalu export jadi xlsx, kembalikan file untuk didownload FE."""
    rows = query_projects.invoke(req.model_dump())
    path = export_to_xlsx(rows)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(path),
    )


@app.get("/health")
def health():
    return {"status": "ok"}