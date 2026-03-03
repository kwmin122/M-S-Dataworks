#!/usr/bin/env python3
"""Step 4: Download and parse official documents.

Downloads PDFs from URLs in official_docs.json, parses with document_parser,
saves text to data/layer1/raw_documents/.
"""
import json
import os
import re
import sys
import tempfile
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(BASE_DIR, "data/layer1/sources/official_docs.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/layer1/raw_documents")

# Add document_parser to path
sys.path.insert(0, BASE_DIR)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def safe_filename(title: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9가-힣_]", "_", title)[:100].strip("_")
    return clean or "unknown"


def download_and_parse(url: str, title: str, fmt: str) -> str | None:
    """Download a document and parse to text."""
    if url.startswith("local://"):
        return None  # These are already manually placed

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return None

        content_type = resp.headers.get("content-type", "")
        # Determine actual format from content-type
        if "pdf" in content_type or fmt.upper() == "PDF":
            ext = ".pdf"
        elif "hwp" in content_type or fmt.upper() == "HWP":
            ext = ".hwp"
        elif "word" in content_type or "docx" in content_type or fmt.upper() == "DOCX":
            ext = ".docx"
        else:
            ext = f".{fmt.lower()}" if fmt else ".pdf"

        # Save to temp file and parse
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        try:
            from document_parser import DocumentParser
            dp = DocumentParser()
            result = dp.parse(tmp_path)
            if result and result.text:
                return result.text
            elif result and result.chunks:
                return "\n\n".join(c.text for c in result.chunks if c.text)
        except (ImportError, Exception):
            # Fallback: try pdfplumber for PDFs
            if ext == ".pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(tmp_path) as pdf:
                        texts = [p.extract_text() or "" for p in pdf.pages]
                        return "\n\n".join(t for t in texts if t)
                except Exception:
                    pass
        finally:
            os.unlink(tmp_path)

    except requests.RequestException as e:
        print(f"  DOWNLOAD ERROR: {e}")
    except Exception as e:
        print(f"  PARSE ERROR: {e}")

    return None


def parse_local_file(filepath: str) -> str | None:
    """Parse a locally placed file."""
    try:
        sys.path.insert(0, BASE_DIR)
        from document_parser import DocumentParser
        dp = DocumentParser()
        result = dp.parse(filepath)
        if result and result.text:
            return result.text
        if result and result.chunks:
            return "\n\n".join(c.text for c in result.chunks if c.text)
    except Exception as e:
        # Fallback for PDF
        if filepath.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    texts = [p.extract_text() or "" for p in pdf.pages]
                    return "\n\n".join(t for t in texts if t)
            except Exception:
                pass
        print(f"  PARSE ERROR: {e}")
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(SOURCES_PATH) as f:
        sources = json.load(f)

    total = len(sources)
    success = 0
    skipped = 0
    total_chars = 0

    print(f"=== Official Document Collection ===")
    print(f"Sources: {total} documents")
    print()

    # First, parse any files already in raw_documents/
    existing_files = [
        f for f in os.listdir(OUTPUT_DIR)
        if f.endswith((".pdf", ".hwp", ".docx")) and not f.endswith(".txt")
    ]
    for fname in existing_files:
        txt_path = os.path.join(OUTPUT_DIR, os.path.splitext(fname)[0] + ".txt")
        if os.path.exists(txt_path) and os.path.getsize(txt_path) > 100:
            continue
        filepath = os.path.join(OUTPUT_DIR, fname)
        print(f"Parsing local file: {fname}...", end="")
        text = parse_local_file(filepath)
        if text and len(text) > 100:
            header = f"# Source: Official Document (Local)\n# File: {fname}\n\n"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(header + text)
            print(f" OK ({len(text):,} chars)")
        else:
            print(f" FAILED")

    # Then process URL sources
    for i, src in enumerate(sources, 1):
        url = src["url"]
        title = src.get("title", "unknown")[:80]
        org = src.get("org", "unknown")
        fmt = src.get("format", "PDF")
        fname = safe_filename(title) + ".txt"
        out_path = os.path.join(OUTPUT_DIR, fname)

        # Skip local:// entries (already handled above)
        if url.startswith("local://"):
            print(f"[{i}/{total}] LOCAL ({org}) {title[:60]} — handled above")
            continue

        # Skip if already collected
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            print(f"[{i}/{total}] CACHED ({org}) {title[:60]}")
            success += 1
            total_chars += os.path.getsize(out_path)
            continue

        print(f"[{i}/{total}] Downloading ({org}) {title[:60]}...", end="")
        text = download_and_parse(url, title, fmt)

        if text and len(text) > 100:
            header = f"# Source: Official Document\n# Org: {org}\n# Title: {title}\n# Year: {src.get('year', '?')}\n# URL: {url}\n\n"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(header + text)
            chars = len(text)
            total_chars += chars
            success += 1
            print(f" OK ({chars:,} chars)")
        else:
            skipped += 1
            print(f" FAILED")

        time.sleep(1.0)

    print()
    print(f"=== Results ===")
    print(f"Downloaded: {success}/{total}")
    print(f"Skipped/Failed: {skipped}")
    print(f"Total chars: {total_chars:,} (~{total_chars // 2:,} tokens)")
    print(f"Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
