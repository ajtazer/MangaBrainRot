# MangaBrainRot

Telegram-driven Instagram Reels poster for MangaDex chapters with AI-generated clickbait thumbnails.

## How it works (main branch)

```
You:  https://mangadex.org/chapter/<uuid>
Bot:  📖 Got "Manga Title — Ch. 12". Add prompt? [🎨 Add prompt] [⏭ Skip thumbnail]

You:  [taps "Add prompt"]
Bot:  📝 Send your thumbnail prompt.

You:  Ayanokoji shirtless, glowing eyes, cracking abs, "WHAT??" overlay
Bot:  🖼 Preview for "Manga Title — Ch. 12". [✅ Post] [🔁 Retry] [❌ Cancel]
       (image attached)

You:  [taps "Post"]
Bot:  🎬 Generating reel with your AI thumbnail. Check Instagram in ~2 min.
```

Per-chat pending state (TTL 5 min) lives in `WF-A`'s static data. `/cancel` aborts an in-progress flow at any point.

## Branches

- **`main`** (this branch) — chapter-driven, on-demand. No queue, no cron, no source list. AI thumbnail prompt is user-supplied per reel; preview shown for confirmation before posting.
- **`sources`** — original auto-poster: track manga *sources*, cron picks one every 4 h, hard-coded clickbait template. Kept for reference.

## Components

| Workflow | Role |
|---|---|
| `WF-A` | Telegram state machine: chapter URL → ask for prompt → preview → confirm → dispatch |
| `WF-B` | Engine: panels → video → conditional AI thumbnail (cover_url) → IG Reels publish |
| `WF-C` | Cron scheduler — **deactivated on `main`** |
| `WF-D` | Static-data store — `posted[]`/`isPosted`/`markPosted` are still used to dedupe |

| Service | Role |
|---|---|
| `manga-api` | FastAPI: MangaDex panel fetcher, ffmpeg renderer (1080×1920), R2 uploader. Hosts `/upload-thumbnail` for AI-generated cover images. |
| `manganow/` | Standalone stdlib-only Python CLI that scrapes `manganow.to` (search, chapter list, page images). Intended as an alternate source feeding into `manga-api`. See `manganow/CONTEXT.md`. |

## Setup

```bash
cp .env.example .env  # fill in R2 + n8n auth + a strong N8N_ENCRYPTION_KEY
docker compose up -d --build
```

Then in n8n UI:

1. Import the four workflow JSONs from `workflows/`.
2. Create credentials referenced by the workflows:
   - **Telegram** (TazedBot): bot token from @BotFather.
   - **Facebook Graph API**: long-lived page token for the IG Business Account; the `share_to_feed` capability on Reels.
   - **HTTP Header Auth** named `IG Bearer`: `Authorization: OAuth <same-token>` — required by `rupload.facebook.com` resumable upload.
   - **OpenAI**: API key with image-generation access (`gpt-image-1`).
3. After import, sub-workflow references between WF-A → WF-B and WF-B → WF-D may be unbound (n8n imports preserve IDs but won't always re-link). Open each `executeWorkflow` node and re-pick the target by name.
4. Activate WF-A and WF-B. Leave WF-C deactivated.
5. Register the Telegram bot's webhook to `https://<your-n8n>/webhook/0f9e01a1-da88-42fc-94ed-cea7c08b246d` (or the new webhookId after import — check in the WF-A trigger node UI).

## Cost notes

- gpt-image-1 medium quality 1024×1536: ~$0.04 per thumbnail.
- Skip path is free.
- ffmpeg render + R2 upload is on your own infra.

## Going back to the auto-poster

`git checkout sources` and re-import workflows. The `sources` branch keeps cron-based auto-posting and the `/add` `/list` `/remove` Telegram commands.
