# MangaBrainRot

Auto-poster pipeline that turns MangaDex chapters into Instagram Reels via n8n + a small FastAPI image renderer.

## Branches

- **`sources`** — original architecture: track manga *sources*, cron picks one every 4h, optional `/add` auto-dispatches first reel. AI thumbnail generated from a hard-coded clickbait template.
- **`main`** — simplified architecture: drop chapter URL into Telegram, bot asks for a thumbnail prompt (or skip via inline button), shows preview, posts on confirm. No queue, no cron.

## Components

| Workflow | Role |
|---|---|
| `WF-A` | Telegram bot (commands → state machine) |
| `WF-B` | Engine: panels → video → AI thumbnail → IG Reels publish |
| `WF-C` | Cron scheduler (deactivated on `main`) |
| `WF-D` | Static-data store (`posted[]` for dedupe; `sources[]`/`queue[]` retained on `sources` branch) |

| Service | Role |
|---|---|
| `manga-api` | FastAPI: fetch MangaDex panels, ffmpeg-render to 1080×1920 reel, upload to R2. Also hosts `/upload-thumbnail` for AI-generated cover images. |

## Setup

```bash
cp .env.example .env  # fill in R2 + n8n auth + a strong N8N_ENCRYPTION_KEY
docker compose up -d --build
```

Then in n8n UI, import the four workflow JSONs from `workflows/` and create the credentials they reference (Telegram bot token, Facebook Graph API, IG Bearer header-auth, OpenAI). Workflow IDs in the JSONs are environment-specific — sub-workflow references will need re-pointing on import.
