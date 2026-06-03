#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


PLACEHOLDER_PATTERNS = (
    "/manganow/images/manganow.jpg",
    "manganow.jpg",
)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
SITEMAP_URL = "https://manganow.to/sitemap.xml"
DEFAULT_CACHE_PATH = Path(__file__).with_name("manganow_manga_index.json")


class ImageURLParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in (
            "src",
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-url",
            "data-image",
        ):
            if attrs.get(name):
                self.urls.append(urljoin(self.base_url, html.unescape(attrs[name])))

        for name in ("srcset", "data-srcset"):
            if attrs.get(name):
                self.urls.extend(parse_srcset(attrs[name], self.base_url))


class ReadingListParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.chapters = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and "reading-item" in attrs.get("class", ""):
            self.current = {
                "id": attrs.get("data-id"),
                "number": attrs.get("data-number"),
                "url": None,
                "title": None,
            }
        elif tag == "a" and self.current is not None:
            href = attrs.get("href")
            if href:
                self.current["url"] = urljoin(self.base_url, href)
            self.current["title"] = attrs.get("title") or attrs.get("data-shortname")

    def handle_endtag(self, tag):
        if tag == "li" and self.current is not None:
            if self.current["id"] and self.current["url"]:
                self.chapters.append(self.current)
            self.current = None


def fetch(url, headers=None, timeout=20):
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers)
    with urlopen(req, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get("content-type", "")
        return body, content_type, response.geturl()


def parse_srcset(value, base_url):
    urls = []
    for chunk in value.split(","):
        candidate = chunk.strip().split(" ", 1)[0]
        if candidate:
            urls.append(urljoin(base_url, html.unescape(candidate)))
    return urls


def extract_raw_image_urls(text, base_url):
    # Also catch URLs embedded in script tags or JSON blobs.
    raw = re.findall(r'https?://[^"\'<>\s]+', text)
    relative = re.findall(r'["\']([^"\']+\.(?:jpe?g|png|webp|gif)(?:\?[^"\']*)?)["\']', text, re.I)
    urls = [html.unescape(url).replace("\\/", "/") for url in raw]
    urls.extend(urljoin(base_url, html.unescape(url).replace("\\/", "/")) for url in relative)
    return urls


def normalize_url(url):
    url = html.unescape(url).replace("\\/", "/")
    url = re.sub(r"\s+", "", url)
    return url.split("#", 1)[0]


def is_candidate_image(url):
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith(IMAGE_EXTENSIONS)


def is_placeholder(url):
    lower = url.lower()
    return any(pattern in lower for pattern in PLACEHOLDER_PATTERNS)


def page_number(url):
    match = re.search(r'/(\d+)\.(?:jpe?g|png|webp|gif)(?:\?|$)', url, re.I)
    return int(match.group(1)) if match else 10**9


def extract_image_urls(chapter_url):
    body, content_type, final_url = fetch(chapter_url)
    text = body.decode("utf-8", errors="replace")
    texts = [text]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and isinstance(payload.get("html"), str):
            texts.append(payload["html"])
    except json.JSONDecodeError:
        pass

    parser = ImageURLParser(final_url)
    for candidate_text in texts:
        parser.feed(candidate_text)

    urls = parser.urls
    for candidate_text in texts:
        urls.extend(extract_raw_image_urls(candidate_text, final_url))
    seen = set()
    deduped = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized not in seen and is_candidate_image(normalized):
            seen.add(normalized)
            deduped.append(normalized)

    real_pages = [
        url for url in deduped
        if not is_placeholder(url) and "/wp-content/uploads/wp-manga/data/" in url.lower()
    ]
    real_pages.sort(key=page_number)
    return final_url, deduped, real_pages


def extract_reader_ids(chapter_url):
    body, _, final_url = fetch(chapter_url)
    text = body.decode("utf-8", errors="replace")
    reading_id = re.search(r'data-reading-id=["\']([^"\']+)["\']', text)
    manga_id = re.search(r'data-manga-id=["\']([^"\']+)["\']', text)
    base_match = re.search(r'"base_url"\s*:\s*"([^"]+)"', text)
    base_url = base_match.group(1).replace("\\/", "/") if base_match else final_url
    return {
        "final_url": final_url,
        "base_url": base_url,
        "reading_id": reading_id.group(1) if reading_id else None,
        "manga_id": manga_id.group(1) if manga_id else None,
    }


def extract_manga_id(manga_url):
    body, _, final_url = fetch(manga_url)
    text = body.decode("utf-8", errors="replace")
    manga_id = re.search(r'data-manga-id=["\']([^"\']+)["\']', text)
    return final_url, manga_id.group(1) if manga_id else None


def get_chapters(manga_url):
    final_url, manga_id = extract_manga_id(manga_url)
    if not manga_id:
        return final_url, None, []
    parsed = urlparse(final_url)
    endpoint = f"{parsed.scheme}://{parsed.netloc}/ajax/reading-list/{manga_id}"
    body, _, _ = fetch(endpoint)
    text = body.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
        chapter_html = payload.get("html", "") if isinstance(payload, dict) else ""
    except json.JSONDecodeError:
        chapter_html = text
    reader = ReadingListParser(final_url)
    reader.feed(chapter_html)
    return final_url, manga_id, reader.chapters


def ajax_image_list_url(base_url, reading_id, mode="vertical"):
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/ajax/image/list/{reading_id}?mode={mode}"


def xml_locs(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    return [
        element.text.strip()
        for element in root.iter()
        if element.tag.endswith("loc") and element.text and element.text.strip()
    ]


def title_from_manga_url(url):
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").title()


def manga_sitemap_urls():
    body, _, _ = fetch(SITEMAP_URL)
    locs = xml_locs(body.decode("utf-8", errors="replace"))
    return [loc for loc in locs if "/sitemap/mangas-" in loc]


def build_manga_index():
    entries = []
    seen = set()
    for sitemap_url in manga_sitemap_urls():
        body, _, _ = fetch(sitemap_url)
        for loc in xml_locs(body.decode("utf-8", errors="replace")):
            if "/manga/" not in loc or loc in seen:
                continue
            slug = urlparse(loc).path.rstrip("/").rsplit("/", 1)[-1].lower()
            # Skip non-series junk: image assets and bare /manga/ listing pages.
            if "/manga/images/" in loc or slug.endswith(IMAGE_EXTENSIONS) or slug == "manga":
                continue
            seen.add(loc)
            entries.append({
                "title": title_from_manga_url(loc),
                "slug": urlparse(loc).path.rstrip("/").rsplit("/", 1)[-1],
                "url": loc,
            })
    entries.sort(key=lambda item: item["title"].lower())
    return entries


def load_manga_index(cache_path=DEFAULT_CACHE_PATH, refresh=False):
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    entries = build_manga_index()
    cache_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def search_manga(query, limit=10, refresh=False):
    query_words = re.findall(r"[a-z0-9]+", query.lower())
    entries = load_manga_index(refresh=refresh)
    scored = []
    for entry in entries:
        haystack = f"{entry['title']} {entry['slug']}".lower()
        score = 0
        for word in query_words:
            if word in haystack:
                score += 2
            if haystack.startswith(word):
                score += 2
        if query.lower() in haystack:
            score += 5
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["title"].lower()))
    return [entry for _, entry in scored[:limit]]


def image_exists(url, referer, timeout=15):
    headers = {
        "Referer": referer,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        body, content_type, _ = fetch(url, headers=headers, timeout=timeout)
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except URLError as exc:
        return False, f"URL error: {exc.reason}"

    if not content_type.lower().startswith("image/"):
        return False, f"not image: {content_type}"
    if len(body) < 512:
        return False, f"tiny body: {len(body)} bytes"
    return True, f"{content_type}, {len(body)} bytes"


def infer_numbered_pages(first_url, referer, max_pages=200, max_misses=3, delay=0.15):
    parsed = urlparse(first_url)
    match = re.match(r"^(?P<base>.*/)(?P<num>\d+)(?P<ext>\.[A-Za-z0-9]+)$", parsed.path)
    if not match:
        return []

    base_url = first_url[: first_url.rfind("/") + 1]
    extension = match.group("ext")
    pages = []
    misses = 0

    for number in range(1, max_pages + 1):
        url = f"{base_url}{number}{extension}"
        ok, detail = image_exists(url, referer)
        print(f"{number:03d} {'OK ' if ok else 'MISS'} {url} ({detail})")
        if ok:
            pages.append(url)
            misses = 0
        else:
            misses += 1
            if pages and misses >= max_misses:
                break
        time.sleep(delay)

    return pages


def resolve_chapter_pages(chapter_url, verbose=False):
    """Return (final_url, ordered_page_urls) for a chapter.

    Tries the chapter HTML first, then falls back to the AJAX image/list
    endpoint, mirroring the resolution used by the CLI's default mode.
    """
    final_url, _all_images, real_pages = extract_image_urls(chapter_url)
    pages = real_pages

    if not pages and "/ajax/image/list/" not in final_url:
        reader = extract_reader_ids(final_url)
        if reader["reading_id"]:
            ajax_url = ajax_image_list_url(reader["base_url"], reader["reading_id"])
            if verbose:
                print(f"  fallback to AJAX images: {ajax_url}")
            _, _, pages = extract_image_urls(ajax_url)

    pages.sort(key=page_number)
    return final_url, pages


def fetch_to_file(url, dest, referer, retries=3, timeout=30, delay=0.4):
    """Download a single image URL to dest with a Referer header and retries.

    Returns (ok, detail). Writes atomically via a temp file.
    """
    headers = {
        "Referer": referer,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    last_error = "unknown error"
    for attempt in range(1, retries + 1):
        try:
            body, content_type, _ = fetch(url, headers=headers, timeout=timeout)
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except URLError as exc:
            last_error = f"URL error: {exc.reason}"
        except (TimeoutError, OSError) as exc:
            last_error = f"network error: {exc}"
        else:
            if not content_type.lower().startswith("image/"):
                last_error = f"not image: {content_type or 'no content-type'}"
            elif len(body) < 512:
                last_error = f"tiny body: {len(body)} bytes"
            else:
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(body)
                tmp.replace(dest)
                return True, f"{content_type}, {len(body)} bytes"
        if attempt < retries:
            time.sleep(delay * attempt)
    return False, last_error


def ext_from_url(url, default=".jpeg"):
    path = urlparse(url).path.lower()
    for extension in IMAGE_EXTENSIONS:
        if path.endswith(extension):
            return extension
    return default


def slug_from_chapter_url(chapter_url):
    parts = [p for p in urlparse(chapter_url).path.split("/") if p]
    # .../manga/<slug>/chapter-<n>
    slug = "manga"
    chapter = "chapter"
    if "manga" in parts:
        idx = parts.index("manga")
        if idx + 1 < len(parts):
            slug = parts[idx + 1]
    for part in parts:
        if part.startswith("chapter"):
            chapter = part
    return slug, chapter


def make_cbz(chapter_dir, files):
    """Bundle downloaded page files into a sibling .cbz archive."""
    cbz_path = chapter_dir.with_suffix(".cbz")
    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_STORED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return cbz_path


def download_chapter(chapter_url, out_dir, delay=0.4, make_archive=False, verbose=True):
    """Resolve and download every page of one chapter. Resumes by skipping
    files that already exist. Returns (count, chapter_dir, saved_files).
    """
    final_url, pages = resolve_chapter_pages(chapter_url, verbose=verbose)
    slug, chapter = slug_from_chapter_url(final_url)
    chapter_dir = Path(out_dir) / slug / chapter
    chapter_dir.mkdir(parents=True, exist_ok=True)

    if not pages:
        print(f"  no pages resolved for {final_url}")
        return 0, chapter_dir, []

    print(f"  {slug}/{chapter}: {len(pages)} page(s) -> {chapter_dir}")
    saved_files = []
    failures = 0
    for index, url in enumerate(pages, 1):
        dest = chapter_dir / f"{index:03d}{ext_from_url(url)}"
        if dest.exists() and dest.stat().st_size >= 512:
            saved_files.append(dest)
            if verbose:
                print(f"    {index:03d} skip (exists)")
            continue
        ok, detail = fetch_to_file(url, dest, referer=final_url, delay=delay)
        status = "OK  " if ok else "FAIL"
        if verbose:
            print(f"    {index:03d} {status} {detail}")
        if ok:
            saved_files.append(dest)
        else:
            failures += 1
        time.sleep(delay)

    if make_archive and saved_files:
        cbz_path = make_cbz(chapter_dir, saved_files)
        print(f"  bundled {len(saved_files)} pages -> {cbz_path}")

    if failures:
        print(f"  {failures} page(s) failed in {chapter}")
    return len(saved_files), chapter_dir, saved_files


def parse_range(spec):
    """Parse '5', '5:10', ':10', '5:' into (low, high) floats; None = open."""
    if ":" not in spec:
        value = float(spec)
        return value, value
    low_text, high_text = spec.split(":", 1)
    low = float(low_text) if low_text.strip() else None
    high = float(high_text) if high_text.strip() else None
    return low, high


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def chapter_in_range(number, bounds):
    if bounds is None:
        return True
    low, high = bounds
    if not _is_number(number):
        return False
    value = float(number)
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


def download_manga(manga_url, out_dir, bounds=None, delay=0.4, make_archive=False):
    """Download a range of chapters for a manga detail URL (oldest-first)."""
    final_url, manga_id, chapters = get_chapters(manga_url)
    if not chapters:
        print(f"No chapters found for {final_url} (manga_id={manga_id})")
        return 1

    selected = [c for c in chapters if chapter_in_range(c["number"], bounds)]
    selected.sort(key=lambda c: float(c["number"]) if _is_number(c["number"]) else 0.0)
    print(f"{final_url}: {len(chapters)} chapter(s), {len(selected)} selected for download")

    total_pages = 0
    for chapter in selected:
        print(f"- chapter {chapter['number']} ({chapter['url']})")
        count, _, _ = download_chapter(
            chapter["url"], out_dir, delay=delay, make_archive=make_archive
        )
        total_pages += count
    print(f"Done. {total_pages} page(s) across {len(selected)} chapter(s).")
    return 0 if total_pages else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--all", action="store_true", help="print every image-ish URL found")
    parser.add_argument("--dump-html", action="store_true", help="print fetched HTML and exit")
    parser.add_argument("--grep", help="print lines containing this text and exit")
    parser.add_argument("--lines", help="print a 1-based line range like 100:130 and exit")
    parser.add_argument("--json", action="store_true", help="print final pages as JSON")
    parser.add_argument("--probe", action="store_true", help="probe numbered pages even if URLs were found")
    parser.add_argument("--search", help="search manga titles from the sitemap index")
    parser.add_argument("--chapters", action="store_true", help="list chapters for a manga detail URL")
    parser.add_argument("--refresh-index", action="store_true", help="rebuild cached sitemap manga index")
    parser.add_argument("--limit", type=int, default=10, help="search result limit")
    parser.add_argument("--download", action="store_true", help="download resolved pages to disk")
    parser.add_argument("--out", default=str(Path(__file__).with_name("outputs")), help="download output directory")
    parser.add_argument("--range", dest="chapter_range", help="chapter range for a manga URL, e.g. 5, 5:10, :10, 100:")
    parser.add_argument("--cbz", action="store_true", help="bundle each downloaded chapter into a .cbz archive")
    parser.add_argument("--delay", type=float, default=0.4, help="delay (seconds) between page requests")
    args = parser.parse_args()

    if args.search:
        results = search_manga(args.search, limit=args.limit, refresh=args.refresh_index)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Found {len(results)} result(s) for {args.search!r}")
            for result in results:
                print(f"- {result['title']} | {result['url']}")
        return 0 if results else 1

    if not args.url:
        parser.error("url is required unless --search is used")

    if args.download:
        bounds = parse_range(args.chapter_range) if args.chapter_range else None
        is_chapter = "/chapter-" in args.url or "/ajax/image/list/" in args.url
        if is_chapter and not args.chapter_range:
            count, chapter_dir, _ = download_chapter(
                args.url, args.out, delay=args.delay, make_archive=args.cbz
            )
            print(f"Downloaded {count} page(s) into {chapter_dir}")
            return 0 if count else 1
        return download_manga(
            args.url, args.out, bounds=bounds, delay=args.delay, make_archive=args.cbz
        )

    if args.chapters:
        final_url, manga_id, chapters = get_chapters(args.url)
        if args.json:
            print(json.dumps({
                "url": final_url,
                "manga_id": manga_id,
                "chapters": chapters[:args.limit],
            }, indent=2))
        else:
            print(f"Fetched: {final_url}")
            print(f"manga_id={manga_id} chapters={len(chapters)}")
            for chapter in chapters[:args.limit]:
                print(f"- {chapter['title']} id={chapter['id']} number={chapter['number']} | {chapter['url']}")
        return 0 if chapters else 1

    if args.dump_html or args.grep or args.lines:
        body, _, final_url = fetch(args.url)
        text = body.decode("utf-8", errors="replace")
        print(f"Fetched: {final_url}", file=sys.stderr)
        if args.lines:
            start_text, end_text = args.lines.split(":", 1)
            start = int(start_text)
            end = int(end_text)
            for line_number, line in enumerate(text.splitlines(), 1):
                if start <= line_number <= end:
                    print(f"{line_number}: {line}")
        elif args.grep:
            needle = args.grep.lower()
            for line_number, line in enumerate(text.splitlines(), 1):
                if needle in line.lower():
                    print(f"{line_number}: {line}")
        else:
            print(text)
        return 0

    final_url, all_images, real_pages = extract_image_urls(args.url)
    print(f"Fetched: {final_url}")
    print(f"Image-ish URLs found: {len(all_images)}")
    print(f"Real WP-manga pages found in HTML: {len(real_pages)}")

    if args.all:
        for url in all_images:
            print(f"CANDIDATE {url}")

    for url in real_pages:
        print(f"HTML {page_number(url):03d} {url}")

    pages = real_pages
    if not pages and "/ajax/image/list/" not in final_url:
        reader = extract_reader_ids(final_url)
        if reader["reading_id"]:
            ajax_url = ajax_image_list_url(reader["base_url"], reader["reading_id"])
            print(f"\nDiscovered reading_id={reader['reading_id']} manga_id={reader['manga_id']}")
            print(f"Fetching AJAX images: {ajax_url}")
            _, _, pages = extract_image_urls(ajax_url)
            for url in pages:
                print(f"AJAX {page_number(url):03d} {url}")

    if (args.probe or len(real_pages) <= 1) and real_pages:
        print("\nProbing numbered page URLs...")
        pages = infer_numbered_pages(real_pages[0], final_url)

    pages.sort(key=page_number)

    if args.json:
        print(json.dumps(pages, indent=2))

    if not pages:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
