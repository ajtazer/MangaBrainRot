# manganow_probe — project context

A single-file, **stdlib-only** Python 3 CLI for the manga aggregator site
`manganow.to`. It searches manga, lists chapters, and resolves the real page
image URLs for a chapter. No third-party dependencies (only `urllib`,
`html.parser`, `xml.etree`, `json`, `re`, `argparse`).

## Files

- `manganow_probe.py` — the tool (≈430 lines).
- `manganow_manga_index.json` — cached search index (~1 MB) built from the
  site's `sitemap.xml`. Safe to delete; regenerate with `--refresh-index`.
- `outputs/` — intended download target (currently empty).

## How the site works (reverse-engineered)

- Manga detail page: `https://manganow.to/manga/<slug>` — carries
  `data-manga-id` in the HTML.
- Chapter list (AJAX): `https://manganow.to/ajax/reading-list/<manga_id>`
  returns JSON `{ "html": "<li class='reading-item' data-id=… data-number=…>…" }`.
- Chapter page: `https://manganow.to/manga/<slug>/chapter-<n>` — carries
  `data-reading-id` and `data-manga-id`. Pages are lazy-loaded, so the HTML
  often has only a placeholder.
- Page images (AJAX): `https://manganow.to/ajax/image/list/<reading_id>?mode=vertical`
  returns the real `<img>` list.
- Real page images are hosted on **mangaread.org**:
  `https://www.mangaread.org/wp-content/uploads/WP-manga/data/manga_<hash>/<hash>/<N>.jpeg`
  (extension can be `.jpeg/.jpg/.png/.webp`).
- Search index: `https://manganow.to/sitemap.xml` → child sitemaps matching
  `/sitemap/mangas-*` → `<loc>` entries containing `/manga/`.

### Important quirks
- Image URLs **require a `Referer` header** (the chapter page URL). Without it
  you get 403/404.
- Page slot **1 is always the lazy placeholder** `manganow/images/manganow.jpg`.
  Real pages start at `/2.jpeg`; `/1.jpeg` is a genuine 404 (confirmed on
  One Piece ch.1141). So derive pages from the AJAX `image/list` response,
  not by assuming page 1 exists.
- Default User-Agent is a desktop Chrome string (see `DEFAULT_HEADERS`).

## Current commands (all tested working as of 2026-06-03)

```bash
# Search titles (offline, uses cached index)
python3 manganow_probe.py --search "one piece" --limit 5
python3 manganow_probe.py --search "one piece" --json --refresh-index

# List chapters for a manga (live)
python3 manganow_probe.py --chapters "https://manganow.to/manga/one-piece" --limit 10
python3 manganow_probe.py --chapters "https://manganow.to/manga/one-piece" --json

# Resolve page image URLs for a chapter (live; auto-falls back to AJAX)
python3 manganow_probe.py "https://manganow.to/manga/one-piece/chapter-1141"
python3 manganow_probe.py "<chapter-url>" --json     # print ordered page URLs as JSON
python3 manganow_probe.py "<chapter-url>" --all      # print every image-ish URL found
python3 manganow_probe.py "<chapter-url>" --probe    # brute-probe sequential page numbers

# Download a single chapter (resumes by skipping existing files)
python3 manganow_probe.py "<chapter-url>" --download
python3 manganow_probe.py "<chapter-url>" --download --cbz          # also bundle a .cbz
python3 manganow_probe.py "<chapter-url>" --download --out ~/manga  # custom output dir

# Download a range of chapters from a manga detail URL (oldest-first)
python3 manganow_probe.py "https://manganow.to/manga/one-piece" --download --range 1140:1141
python3 manganow_probe.py "<manga-url>" --download --range :10     # chapters up to 10
python3 manganow_probe.py "<manga-url>" --download --range 100:    # chapters from 100 on
python3 manganow_probe.py "<manga-url>" --download --range 5 --cbz --delay 0.2

# Debug helpers
python3 manganow_probe.py "<url>" --dump-html
python3 manganow_probe.py "<url>" --grep data-reading-id
python3 manganow_probe.py "<url>" --lines 100:130
```

Downloads land in `outputs/<manga-slug>/chapter-<n>/NNN.<ext>` (default `--out`
is the `outputs/` folder next to the script). Pages download with the chapter
URL as `Referer`, retry up to 3 times on transient errors, validate
content-type/size, and write atomically via a `.part` temp file. `--cbz`
produces `outputs/<slug>/chapter-<n>.cbz` (a plain zip of the page images).

### Internals worth knowing
- `search_manga()` / `load_manga_index()` / `build_manga_index()` — sitemap index.
  The builder now skips junk `loc`s (`/manga/images/…`, image-extension slugs,
  the bare `/manga` listing) so the index is real series only.
- `get_chapters()` → `extract_manga_id()` + `/ajax/reading-list/`.
- `extract_image_urls()` — HTML + raw-regex + AJAX-JSON `html` field; filters to
  `/wp-content/uploads/wp-manga/data/`, drops placeholders, sorts by page number.
- `resolve_chapter_pages()` — reusable HTML→AJAX page resolution (shared by the
  default CLI mode and the downloader).
- `extract_reader_ids()` — pulls `data-reading-id`, `data-manga-id`, `base_url`.
- `image_exists()` — HEAD-ish GET with Referer; validates `content-type`/size.
- `infer_numbered_pages()` — sequential probe with miss tolerance.

### Downloader internals
- `fetch_to_file()` — download one image with Referer, retries (3x, backoff),
  content-type/size validation, atomic `.part`→final rename.
- `download_chapter()` — resolve pages, write `NNN.<ext>`, resume by skipping
  existing files, optional `--cbz` bundling. Returns `(count, dir, files)`.
- `download_manga()` — iterate `get_chapters()`, filter by `--range`, download
  oldest-first.
- `parse_range()` / `chapter_in_range()` — `"5"`, `"5:10"`, `":10"`, `"100:"`.
- `make_cbz()` — zip page images into `chapter-<n>.cbz`.

## Possible future work

- Content-sniffed extensions (host serves `.jpeg` URLs that are actually webp;
  files are currently named from the URL extension).
- PDF bundling (CBZ is implemented).
- Concurrency / parallel page fetches (currently sequential with `--delay`).

## Running on Ubuntu

Only needs Python 3 (3.8+). No pip installs required.

```bash
python3 manganow_probe.py --search "naruto"
```
