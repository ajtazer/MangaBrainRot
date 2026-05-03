import asyncio
import base64
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from generator import _upload_r2, generate_reel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("manga-api")

app = FastAPI(title="manga-api", version="1.0.0")


class GenerateRequest(BaseModel):
    chapter_id: str
    bgm_url: str
    callback_url: str
    cover_url: Optional[str] = None
    max_panels: int = 12
    seconds_per_panel: float = 3.0


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    log.info("queued job %s for chapter %s", job_id, req.chapter_id)
    background_tasks.add_task(_run_job, job_id, req)
    return {"job_id": job_id, "status": "queued"}


async def _run_job(job_id: str, req: GenerateRequest):
    try:
        log.info("[%s] starting generation", job_id)
        video_url = await asyncio.to_thread(
            generate_reel,
            job_id,
            req.chapter_id,
            req.bgm_url,
            req.cover_url,
            req.max_panels,
            req.seconds_per_panel,
        )
        log.info("[%s] done -> %s", job_id, video_url)
        await _callback(req.callback_url, {"job_id": job_id, "video_url": video_url})
    except Exception as e:
        log.exception("[%s] failed: %s", job_id, e)
        await _callback(req.callback_url, {"job_id": job_id, "error": str(e)})


class UploadThumbnailRequest(BaseModel):
    b64: str
    content_type: str = "image/png"
    key_prefix: str = "thumbnails"


@app.post("/upload-thumbnail")
async def upload_thumbnail(req: UploadThumbnailRequest):
    try:
        data = base64.b64decode(req.b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid base64: {e}")
    if not data:
        raise HTTPException(status_code=400, detail="empty image")

    ext = "png" if req.content_type.endswith("png") else "jpg"
    work_dir = Path(tempfile.mkdtemp(prefix="thumb-"))
    try:
        local = work_dir / f"{uuid.uuid4()}.{ext}"
        local.write_bytes(data)
        key = f"{req.key_prefix}/{local.name}"
        url = await asyncio.to_thread(_upload_r2, local, key, req.content_type)
        log.info("uploaded thumbnail -> %s (%d bytes)", url, len(data))
        return {"url": url}
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


async def _callback(url: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            log.info("callback %s -> %s", url, r.status_code)
    except Exception as e:
        log.exception("callback failed: %s", e)
