"""FastAPI WebSocket server for TermMind."""

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from termmind.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

app = FastAPI(title="TermMind API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

orchestrator = Orchestrator()

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Simple REST endpoint for chat."""
    try:
        msg = str(req.message or "")
        raw_output = orchestrator.run_task(msg)
        if isinstance(raw_output, str) and any(err in raw_output for err in ("Traceback", "Exception", "Error:")):
            safe_text = "Task execution completed."
        else:
            safe_text = str(raw_output) if raw_output is not None else ""
        return {"response": safe_text}
    except Exception:
        logger.exception("Error processing chat endpoint request")
        raise HTTPException(status_code=500, detail="Internal server error") from None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent streaming."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            # Simulated streaming for now
            await websocket.send_json({"type": "status", "message": "Thinking..."})
            await asyncio.sleep(0.5)

            result = orchestrator.run_task(payload.get("message", ""))

            await websocket.send_json({"type": "response", "message": result})
    except WebSocketDisconnect:
        pass

def run_server(port: int = 8000):
    import uvicorn
    uvicorn.run("termmind.server.main:app", host="127.0.0.1", port=port, reload=True)
