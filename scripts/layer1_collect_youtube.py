#!/usr/bin/env python3
"""Step 2: Collect YouTube transcripts from curated sources.

Reads data/layer1/sources/youtube_sources.json, fetches Korean transcripts
via youtube-transcript-api v1.x, saves to data/layer1/raw_transcripts/.
"""
import json
import os
import sys
import time

from youtube_transcript_api import YouTubeTranscriptApi

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(BASE_DIR, "data/layer1/sources/youtube_sources.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/layer1/raw_transcripts")


def fetch_transcript(api: YouTubeTranscriptApi, video_id: str) -> str | None:
    """Fetch Korean transcript using youtube-transcript-api v1.x API."""
    # Try direct fetch with Korean language preference
    try:
        result = api.fetch(video_id, languages=["ko"])
        text = "\n".join(snippet.text for snippet in result.snippets)
        if text and len(text) > 30:
            return text
    except Exception:
        pass

    # Fallback: list available transcripts and try translation
    try:
        transcript_list = api.list(video_id)
        for t in transcript_list:
            try:
                translated = t.translate("ko").fetch()
                text = "\n".join(snippet.text for snippet in translated.snippets)
                if text and len(text) > 30:
                    return text
            except Exception:
                continue
    except Exception as e:
        print(f"  SKIP {video_id}: {e}")
        return None

    print(f"  SKIP {video_id}: no Korean transcript available")
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(SOURCES_PATH) as f:
        sources = json.load(f)

    total = len(sources)
    success = 0
    skipped = 0
    total_chars = 0

    api = YouTubeTranscriptApi()

    print(f"=== YouTube Transcript Collection ===")
    print(f"Sources: {total} videos")
    print()

    for i, src in enumerate(sources, 1):
        vid = src["id"]
        title = src.get("title", "unknown")[:60]
        grade = src.get("grade", "?")
        out_path = os.path.join(OUTPUT_DIR, f"{vid}.txt")

        # Skip if already collected
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            print(f"[{i}/{total}] CACHED {vid} ({grade}) {title}")
            success += 1
            total_chars += os.path.getsize(out_path)
            continue

        print(f"[{i}/{total}] Fetching {vid} ({grade}) {title}...", end="")
        text = fetch_transcript(api, vid)

        if text and len(text) > 50:
            # Prepend metadata
            header = f"# Source: YouTube\n# Video ID: {vid}\n# Grade: {grade}\n# Title: {title}\n# Channel: {src.get('channel', 'unknown')}\n\n"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(header + text)
            chars = len(text)
            total_chars += chars
            success += 1
            print(f" OK ({chars:,} chars)")
        else:
            skipped += 1
            print(f" EMPTY/SKIP")

        # Rate limit: be nice to YouTube
        time.sleep(0.5)

    print()
    print(f"=== Results ===")
    print(f"Success: {success}/{total}")
    print(f"Skipped: {skipped}")
    print(f"Total chars: {total_chars:,} (~{total_chars // 2:,} tokens)")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
