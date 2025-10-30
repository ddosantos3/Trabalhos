# backend/api/chat_agent_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os

from agent.chat_agent import ChatAgent

router = APIRouter()

# ajustar data_dir para seu backend/data
HERE = Path(__file__).resolve().parents[1]  # backend/
DATA_DIR = HERE / "data"

# instância singleton do agente
agent = ChatAgent(data_dir=DATA_DIR)

class ChatRequest(BaseModel):
    message: str
    dashboard_analysis: str | None = None
    top_k: int | None = 6
    temperature: float | None = None

@router.post("/agent/chat")
async def post_chat(req: ChatRequest):
    try:
        result = agent.answer(
            user_message=req.message,
            top_k=req.top_k or 6,
            dashboard_analysis=req.dashboard_analysis,
            temperature=req.temperature
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/reload")
async def reload_index():
    try:
        agent.reload_documents()
        return {"status": "ok", "loaded_chunks": len(agent.chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
