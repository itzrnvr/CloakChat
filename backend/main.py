import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import load_config
from backend.routes import chat, config

app = FastAPI(title="CloakChat", description="Privacy-preserving AI chat", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,   prefix="/api", tags=["chat"])
app.include_router(config.router, prefix="/api", tags=["config"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    cfg = load_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg.server.get("host", "0.0.0.0"),
        port=cfg.server.get("port", 8001),
        reload=True,
    )
