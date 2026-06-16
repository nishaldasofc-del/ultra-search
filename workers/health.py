"""
Worker health check — exposes /health for each worker process
"""

import asyncio
from fastapi import FastAPI
import uvicorn
from workers.tasks import celery_app

app = FastAPI(title="Worker Health")


@app.get("/health")
async def health():
    inspect = celery_app.control.inspect(timeout=2)
    active = inspect.active() or {}
    return {
        "status": "ok",
        "workers": list(active.keys()),
        "active_tasks": sum(len(v) for v in active.values()),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
