#!/usr/bin/env python3
"""Step 3: Collect blog content from curated sources.

Reads data/layer1/sources/blog_sources.json, fetches content via trafilatura,
saves to data/layer1/raw_blogs/.
"""
import hashlib
import json
import os
import re
import time

import trafilatura

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(BASE_DIR, "data/layer1/sources/blog_sources.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/layer1/raw_blogs")

# Some sites block bots; set realistic headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def safe_filename(title: str, url: str) -> str:
    """Create a safe filename from title or URL hash."""
    clean = re.sub(r"[^a-zA-Z0-9가-힣]", "_", title)[:80].strip("_")
    if not clean:
        clean = hashlib.md5(url.encode()).hexdigest()[:12]
    return clean


def fetch_blog(url: str) -> str | None:
    """Fetch and extract blog content using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        return text
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(SOURCES_PATH) as f:
        sources = json.load(f)

    total = len(sources)
    success = 0
    skipped = 0
    total_chars = 0

    print(f"=== Blog Content Collection ===")
    print(f"Sources: {total} URLs")
    print()

    for i, src in enumerate(sources, 1):
        url = src["url"]
        title = src.get("title", "unknown")[:60]
        category = src.get("category", "?")
        fname = safe_filename(title, url) + ".txt"
        out_path = os.path.join(OUTPUT_DIR, fname)

        # Skip if already collected
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            print(f"[{i}/{total}] CACHED ({category}) {title[:50]}")
            success += 1
            total_chars += os.path.getsize(out_path)
            continue

        print(f"[{i}/{total}] Fetching ({category}) {title[:50]}...", end="")
        text = fetch_blog(url)

        if text and len(text) > 200:
            header = f"# Source: Blog\n# URL: {url}\n# Title: {title}\n# Category: {category}\n# Quality: {src.get('quality', '?')}\n\n"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(header + text)
            chars = len(text)
            total_chars += chars
            success += 1
            print(f" OK ({chars:,} chars)")
        else:
            skipped += 1
            print(f" EMPTY/BLOCKED")

        # Rate limit
        time.sleep(1.0)

    print()
    print(f"=== Results ===")
    print(f"Success: {success}/{total}")
    print(f"Skipped: {skipped}")
    print(f"Total chars: {total_chars:,} (~{total_chars // 2:,} tokens)")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
