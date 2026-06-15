"""FastAPI WebSocket server for TermMind."""

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from termmind.agents.orchestrator import Orchestrator

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
    response = orchestrator.run_task(req.message)
    return {"response": response}

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
