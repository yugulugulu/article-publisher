# -*- coding: utf-8 -*-
"""Test: fetch real Odaily daily report, transform, save draft with tag + user_id=6."""

import json
import logging
import sys
import os
import yaml
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import requests
from pipelines import create_scrapers
from services.daily_report import DailyReportScheduler
from services.publisher import Publisher
from utils.cos import COSUploader

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")


def main():
    base_dir = Path(os.path.join(os.path.dirname(__file__), "..")).resolve()
    with open(base_dir / "config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ct = cfg["chainthink"]
    token = os.environ.get("CHAINTHINK_TOKEN", ct.get("token", ""))

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=utf-8",
        "Origin": "https://admin.chainthink.cn",
        "Referer": "https://admin.chainthink.cn/",
        "User-Agent": "Mozilla/5.0",
        "x-token": token,
        "x-user-id": str(ct.get("user_id", "")),
        "X-App-Id": str(ct.get("app_id", "")),
    }

    session = requests.Session()
    cos = COSUploader(
        upload_url=ct["upload_url"],
        api_headers=headers,
        session=session,
        x_app_id=str(ct.get("app_id", "")),
    )
    publisher = Publisher(
        api_url=ct["api_url"],
        api_headers=headers,
        cos_uploader=cos,
    )

    # Step 1: Fetch from Odaily
    scrapers = create_scrapers(cfg, session, base_dir)
    scraper = scrapers.get("odaily")
    if not scraper:
        print("ERROR: odaily scraper not found")
        return

    print("Fetching Odaily article list...")
    items = scraper.parse_list()
    print(f"Got {len(items)} items")

    # Find the daily report article (24H热门币种与要闻)
    daily_item = None
    today_str = datetime.now().strftime("%Y-%m-%d")

    for item in items:
        title = item.get("title", "")
        print(f"  - {title[:60]}")
        if "24H" in title and "热门" in title:
            if DailyReportScheduler._is_published_today(item, today_str):
                daily_item = item
                break
            else:
                print(f"    (not today, skipping)")

    if not daily_item:
        print("Daily report not found in today's articles!")
        return

    print(f"\nFound daily report: {daily_item.get('title', '')[:80]}")
    article_id = daily_item.get("article_id", "")
    print(f"Article ID: {article_id}")

    # Step 2: Fetch full detail
    print("\nFetching full detail...")
    detail = scraper.fetch_detail(daily_item)
    print(f"Title: {detail.get('title', '')}")
    print(f"Blocks: {len(detail.get('blocks', []))}")

    # Step 3: Transform (inline, same logic as DailyReportScheduler._transform_daily_report)
    blocks = detail.get("blocks", [])
    toutiao_idx = None
    for i, block in enumerate(blocks):
        text = block.get("text", "").strip()
        if "头条" in text:
            toutiao_idx = i
            break
    if toutiao_idx is not None:
        blocks = blocks[toutiao_idx:]
    blocks = DailyReportScheduler._strip_trailing_author_source(blocks)

    now = datetime.now()
    transformed = {
        **detail,
        "title": f"ChainThink{now.month}.{now.day}早报",
        "author": "",
        "source": "",
        "blocks": blocks,
        "cover_src": "",
        "abstract": "",
        "user_id": "6",
        "strong_content_tags": {"人工": ["加密早报"]},
    }
    print(f"\nTransformed title: {transformed['title']}")
    print(f"Transformed blocks: {len(transformed.get('blocks', []))}")

    # Step 4: Upload cover
    cover_path = base_dir / "data" / "daily_report_cover.png"
    if cover_path.exists():
        print(f"\nUploading cover from {cover_path}...")
        cos_url = cos.upload_cover_from_file(str(cover_path))
        if cos_url:
            transformed["cover_src"] = cos_url
            print(f"Cover uploaded: {cos_url}")
        else:
            print("Cover upload returned empty")
    else:
        print(f"\nNo cover at {cover_path}")

    # Step 5: Generate abstract via LLM
    try:
        from services.llm import generate_abstract
        from services.database import ArticleDatabase

        db_path = cfg.get("database", {}).get("sqlite_path")
        db = ArticleDatabase(base_dir / db_path) if db_path else None
        ai_abstract = generate_abstract(transformed, db)
        if ai_abstract:
            transformed["abstract"] = ai_abstract
            print(f"\nAbstract generated: {ai_abstract[:80]}...")
    except Exception as exc:
        print(f"\nAbstract generation skipped: {exc}")

    if not transformed.get("abstract"):
        # Build a fallback abstract from first few text blocks
        texts = [b["text"].strip() for b in transformed["blocks"] if b.get("text")][:3]
        transformed["abstract"] = "。".join(texts)[:180]

    # Step 6: Save as draft (not published)
    print("\n--- Saving DRAFT ---")
    print(f"  user_id: {transformed.get('user_id')}")
    print(f"  tags: {transformed.get('strong_content_tags')}")
    result = publisher.save_draft(transformed)
    print(f"\nDraft saved! CMS ID: {result['cms_id']}")
    print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
