#!/usr/bin/env python3
"""Step 7: Augment Layer 1 knowledge with web search results.

Uses googlesearch-python to find additional high-quality content about
Korean public procurement proposal writing, then fetches and filters
via trafilatura.

Usage:
  pip install googlesearch-python trafilatura
  python scripts/layer1_augment_web.py
"""
import hashlib
import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data/layer1/raw_blogs")
SOURCES_PATH = os.path.join(BASE_DIR, "data/layer1/sources/blog_sources.json")

# Korean search queries targeting proposal writing knowledge
SEARCH_QUERIES = [
    "공공조달 제안서 작성 방법 팁",
    "기술제안서 작성 요령 공사 용역",
    "나라장터 입찰 제안서 핵심 전략",
    "제안서 평가기준 배점 높은 점수 받는법",
    "공공기관 제안서 평가위원 관점",
    "IT 공공사업 제안서 사업이해 수행전략",
    "제안서 프레젠테이션 PT 발표 전략",
    "조달청 용역 입찰 자격요건 체크리스트",
    "공공조달 컨소시엄 제안서 작성",
    "제안서 기술성 평가 고득점 사례",
    "정보화사업 제안서 WBS 일정 작성법",
    "공공 SI 프로젝트 제안서 인력구성 방법",
]

# Quality filter keywords — at least 2 must appear
QUALITY_KEYWORDS = [
    "제안서", "입찰", "평가", "배점", "기술", "공공", "조달",
    "나라장터", "수행", "사업", "요구사항", "요건", "프레젠테이션",
    "컨소시엄", "실적", "자격", "제출", "발주", "공고",
]

MIN_CONTENT_LENGTH = 500


def load_existing_urls() -> set[str]:
    """Load already-collected URLs to avoid duplicates."""
    urls: set[str] = set()
    # From blog sources
    if os.path.isfile(SOURCES_PATH):
        with open(SOURCES_PATH) as f:
            for item in json.load(f):
                urls.add(item.get("url", ""))
    # From already-downloaded files (check metadata)
    for fname in os.listdir(OUTPUT_DIR) if os.path.isdir(OUTPUT_DIR) else []:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if fname.endswith(".txt") and os.path.isfile(fpath):
            with open(fpath, encoding="utf-8", errors="ignore") as f:
                first_line = f.readline()
                if first_line.startswith("# URL:"):
                    urls.add(first_line.replace("# URL:", "").strip())
    return urls


def search_google(query: str, num_results: int = 10) -> list[str]:
    """Search Google and return URLs."""
    try:
        from googlesearch import search
        results = list(search(query, num_results=num_results, lang="ko"))
        return results
    except Exception as e:
        print(f"  Search error for '{query}': {e}")
        return []


def fetch_content(url: str) -> str | None:
    """Fetch and extract main content from URL."""
    try:
        import trafilatura
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
        print(f"  Fetch error: {e}")
        return None


def passes_quality_filter(text: str) -> bool:
    """Check if content is relevant to proposal writing."""
    if len(text) < MIN_CONTENT_LENGTH:
        return False
    matches = sum(1 for kw in QUALITY_KEYWORDS if kw in text)
    return matches >= 2


def safe_filename(url: str) -> str:
    """Create safe filename from URL hash."""
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"web_{h}"


# Curated URLs for direct fetch (known high-quality Korean proposal content)
CURATED_URLS = [
    "https://brunch.co.kr/@expertb2b/42",
    "https://brunch.co.kr/@expertb2b/43",
    "https://brunch.co.kr/@expertb2b/44",
    "https://brunch.co.kr/@expertb2b/45",
    "https://brunch.co.kr/@expertb2b/46",
    "https://brunch.co.kr/@expertb2b/47",
    "https://brunch.co.kr/@expertb2b/48",
    "https://brunch.co.kr/@itrendlab/30",
    "https://brunch.co.kr/@itrendlab/31",
    "https://brunch.co.kr/@itrendlab/32",
    "https://brunch.co.kr/@itrendlab/33",
    "https://brunch.co.kr/@itrendlab/34",
    "https://brunch.co.kr/@itrendlab/77",
    "https://brunch.co.kr/@itrendlab/78",
    "https://brunch.co.kr/@itrendlab/79",
    "https://brunch.co.kr/@itrendlab/80",
    "https://brunch.co.kr/@hjkim0892/193",
    "https://brunch.co.kr/@hjkim0892/194",
    "https://brunch.co.kr/@hjkim0892/195",
    "https://brunch.co.kr/@hjkim0892/196",
    "https://brunch.co.kr/@hjkim0892/197",
    "https://brunch.co.kr/@hjkim0892/198",
    "https://brunch.co.kr/@hjkim0892/200",
    "https://brunch.co.kr/@hjkim0892/201",
    "https://brunch.co.kr/@bedreamer/1086",
    "https://brunch.co.kr/@bedreamer/1087",
    "https://brunch.co.kr/@bedreamer/1088",
    "https://brunch.co.kr/@bedreamer/1084",
    "https://brunch.co.kr/@nadaumbrand/48",
    "https://brunch.co.kr/@nadaumbrand/49",
    "https://brunch.co.kr/@nadaumbrand/50",
    "https://proposal6852.tistory.com/entry/정보시스템-제안서-보안-관리-작성",
    "https://proposal6852.tistory.com/entry/정보시스템-제안서-품질관리-방법",
    "https://proposal6852.tistory.com/entry/제안서-추진일정표-작성-가이드",
    "https://proposal6852.tistory.com/entry/제안서-사업관리-작성법",
    "https://proposal6852.tistory.com/entry/제안서-유사실적-작성법",
    "https://proposal6852.tistory.com/entry/정보시스템-제안서-WBS-작성",
    "https://proposal6852.tistory.com/entry/정보시스템-제안서-사업이해-작성",
    "https://proposal6852.tistory.com/entry/정보시스템-제안서-조직구성",
    "https://proposal6852.tistory.com/entry/제안서-PT-프레젠테이션-발표-전략",
    "https://proposal6852.tistory.com/entry/제안서-기술점수-평가-배점-분석",
    "https://islppt.tistory.com/entry/제안서-PPT-디자인-비주얼-가이드",
    "https://islppt.tistory.com/entry/입찰-제안서-핵심구조",
    "https://islppt.tistory.com/entry/정보화사업-제안서-작성-구조",
    "https://wellobiz.tistory.com/28",
    "https://wellobiz.tistory.com/29",
    "https://wellobiz.tistory.com/30",
    "https://wellobiz.tistory.com/31",
    "https://chingguhl.tistory.com/entry/공공조달-입찰-절차-완벽-가이드",
    "https://chingguhl.tistory.com/entry/나라장터-입찰-참가자격-요건-체크리스트",
]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    existing_urls = load_existing_urls()
    print(f"Existing URLs: {len(existing_urls)}")

    new_urls: list[dict] = []
    all_candidate_urls: set[str] = set()

    # Phase 1: Collect URLs from Google search + curated list
    print("\n=== Phase 1: Searching Google + curated URLs ===")
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"[{i+1}/{len(SEARCH_QUERIES)}] Searching: {query}")
        urls = search_google(query, num_results=10)
        for url in urls:
            if url not in existing_urls and url not in all_candidate_urls:
                all_candidate_urls.add(url)
        time.sleep(2)  # Rate limiting

    # Add curated URLs
    for url in CURATED_URLS:
        if url not in existing_urls and url not in all_candidate_urls:
            all_candidate_urls.add(url)

    print(f"\nCandidate URLs (after dedup): {len(all_candidate_urls)}")

    # Phase 2: Fetch and filter
    print("\n=== Phase 2: Fetching & filtering ===")
    success = 0
    filtered = 0
    errors = 0

    for i, url in enumerate(sorted(all_candidate_urls)):
        print(f"[{i+1}/{len(all_candidate_urls)}] {url[:80]}")
        text = fetch_content(url)
        if not text:
            errors += 1
            print("  -> SKIP (fetch failed)")
            continue

        if not passes_quality_filter(text):
            filtered += 1
            print(f"  -> SKIP (quality filter, {len(text)} chars)")
            continue

        # Save raw text with metadata header
        fname = safe_filename(url)
        out_path = os.path.join(OUTPUT_DIR, f"{fname}.txt")
        if os.path.exists(out_path):
            print("  -> SKIP (already exists)")
            continue

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# URL: {url}\n")
            f.write(f"# Source: web_search\n")
            f.write(f"# Length: {len(text)}\n\n")
            f.write(text)

        success += 1
        new_urls.append({"url": url, "title": fname, "source": "web_search"})
        print(f"  -> SAVED ({len(text)} chars)")

        time.sleep(1)  # Rate limiting

    # Phase 3: Update sources JSON
    if new_urls:
        print(f"\n=== Phase 3: Updating sources ===")
        sources = []
        if os.path.isfile(SOURCES_PATH):
            with open(SOURCES_PATH) as f:
                sources = json.load(f)
        sources.extend(new_urls)
        with open(SOURCES_PATH, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        print(f"Updated {SOURCES_PATH}: {len(sources)} total sources")

    # Summary
    print(f"\n=== Summary ===")
    print(f"Candidates searched: {len(all_candidate_urls)}")
    print(f"Successfully saved: {success}")
    print(f"Filtered (quality): {filtered}")
    print(f"Errors: {errors}")
    print(f"\nNext steps:")
    print(f"  1. python scripts/layer1_extract_knowledge.py")
    print(f"  2. python scripts/layer1_refine_knowledge.py")
    print(f"  3. python scripts/layer1_build_vectordb.py")


if __name__ == "__main__":
    main()
