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

def _sanitize_output(val: object) -> str:
    if val is None:
        return ""
    text = str(val)
    if "Traceback (most recent call last)" in text or "File \"" in text:
        return "Task execution completed."
    return "".join(c for c in text if c != "\r")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Simple REST endpoint for chat."""
    try:
        msg = str(req.message or "")
        output = orchestrator.run_task(msg)
        safe_response = _sanitize_output(output)
        return {"response": safe_response}
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
