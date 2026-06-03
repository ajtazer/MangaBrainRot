import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import boto3
import httpx
from botocore.config import Config
from PIL import Image

import manganow_probe as manganow

log = logging.getLogger("manga-api.generator")

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "manga-videos")
R2_PUBLIC_URL = os.environ.get(
    "R2_PUBLIC_URL", "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev"
)

MANGADEX_API = "https://api.mangadex.org"
TARGET_W, TARGET_H = 1080, 1920


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _fetch_panels(chapter_id: str, work_dir: Path, max_panels: int) -> list[Path]:
    """Download up to `max_panels` page images for a chapter.

    Accepts either a MangaDex chapter UUID or a manganow chapter URL
    (e.g. https://manganow.to/manga/<slug>/chapter-<n>).
    """
    if chapter_id.startswith("http"):
        return _fetch_panels_manganow(chapter_id, work_dir, max_panels)
    return _fetch_panels_mangadex(chapter_id, work_dir, max_panels)


def _fetch_panels_mangadex(chapter_id: str, work_dir: Path, max_panels: int) -> list[Path]:
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        r = c.get(f"{MANGADEX_API}/at-home/server/{chapter_id}")
        r.raise_for_status()
        data = r.json()
        base_url = data["baseUrl"]
        chapter_hash = data["chapter"]["hash"]
        filenames = data["chapter"]["data"][:max_panels]

        paths = []
        for idx, fname in enumerate(filenames):
            url = f"{base_url}/data/{chapter_hash}/{fname}"
            local = work_dir / f"panel_{idx:03d}{Path(fname).suffix.lower() or '.jpg'}"
            log.info("fetch panel %d/%d %s", idx + 1, len(filenames), url)
            resp = c.get(url)
            resp.raise_for_status()
            local.write_bytes(resp.content)
            paths.append(local)
        return paths


def _fetch_panels_manganow(chapter_url: str, work_dir: Path, max_panels: int) -> list[Path]:
    """Fetch panels from manganow.to (delegates to manganow_probe).

    manganow image URLs require the chapter URL as Referer.
    """
    final_url, pages = manganow.resolve_chapter_pages(chapter_url)
    if not pages:
        raise RuntimeError(f"manganow: no pages resolved for {chapter_url}")
    pages = pages[:max_panels]

    headers = {
        **manganow.DEFAULT_HEADERS,
        "Referer": final_url,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    paths = []
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as c:
        for idx, url in enumerate(pages):
            ext = manganow.ext_from_url(url, default=".jpg")
            local = work_dir / f"panel_{idx:03d}{ext}"
            log.info("fetch manganow panel %d/%d %s", idx + 1, len(pages), url)
            resp = c.get(url)
            resp.raise_for_status()
            local.write_bytes(resp.content)
            paths.append(local)
    return paths


def _resize_to_reel(panels: list[Path], work_dir: Path) -> list[Path]:
    out = []
    for idx, src in enumerate(panels):
        try:
            img = Image.open(src)
        except Exception as e:
            log.warning("skip unreadable panel %s: %s", src, e)
            continue
        if img.mode != "RGB":
            bg = Image.new("RGB", img.size, (0, 0, 0))
            try:
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            except Exception:
                img = img.convert("RGB")
        ratio = min(TARGET_W / img.width, TARGET_H / img.height)
        new_w, new_h = int(img.width * ratio), int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
        canvas.paste(img, ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2))
        dst = work_dir / f"frame_{idx:03d}.jpg"
        canvas.save(dst, "JPEG", quality=92)
        out.append(dst)
    return out


def _download(url: str, dst: Path):
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        dst.write_bytes(r.content)


def _ffmpeg_render(
    frames_dir: Path, bgm_path: Path, out_path: Path, seconds_per_panel: float
):
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate", f"1/{seconds_per_panel}",
        "-i", str(frames_dir / "frame_%03d.jpg"),
        "-i", str(bgm_path),
        "-vf",
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"format=yuv420p,setsar=1,setrange=tv",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.0",
        "-preset", "veryfast",
        "-crf", "23",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path),
    ]
    log.info("ffmpeg: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("ffmpeg stderr:\n%s", proc.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode})")


def _upload_r2(local: Path, key: str, content_type: str = "video/mp4") -> str:
    client = _r2_client()
    client.upload_file(
        str(local),
        R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{R2_PUBLIC_URL}/{key}"


def generate_reel(
    job_id: str,
    chapter_id: str,
    bgm_url: str,
    cover_url: str | None,
    max_panels: int,
    seconds_per_panel: float,
) -> str:
    work_dir = Path(tempfile.mkdtemp(prefix=f"manga-{job_id}-"))
    try:
        log.info("[%s] work dir: %s", job_id, work_dir)

        raw_panels = _fetch_panels(chapter_id, work_dir, max_panels)
        if not raw_panels:
            raise RuntimeError("no panels fetched from MangaDex")

        frames_dir = work_dir / "frames"
        frames_dir.mkdir()
        for i, src in enumerate(raw_panels):
            shutil.move(str(src), frames_dir / f"raw_{i:03d}{src.suffix}")
        raw_in_frames = sorted(frames_dir.glob("raw_*"))

        resized = _resize_to_reel(raw_in_frames, frames_dir)
        if not resized:
            raise RuntimeError("no panels survived resize")
        for src in raw_in_frames:
            src.unlink(missing_ok=True)

        bgm_path = work_dir / "bgm.mp3"
        _download(bgm_url, bgm_path)

        out_path = work_dir / "reel.mp4"
        _ffmpeg_render(frames_dir, bgm_path, out_path, seconds_per_panel)

        key = f"videos/{job_id}.mp4"
        url = _upload_r2(out_path, key)
        return url
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
