"""social_search.py · reverse‑image search helper

Workflow:
1. Upload the photo bytes to **Cloudinary** (transient folder `missing_finder/`)
2. Pass the resulting public `secure_url` to SerpAPI “Google Lens” engine
3. Filter visual‑match links for major social‑media domains and return at most
   *max_sites* entries as `[{'title': str, 'url': str}, …]`.

Environment variables required (put in **.env** or host secrets):
```
SERPAPI_KEY=xxxxxxxxxxxxxxxxxxxx
CLOUDINARY_CLOUD_NAME=demo
CLOUDINARY_API_KEY=123456789
CLOUDINARY_API_SECRET=aaaaaaaaaaaaaaaaaaaa
```
"""
from __future__ import annotations

import os
from typing import Dict, List

import cloudinary
import cloudinary.uploader
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()  # load .env variables if present

# ── API keys / config ───────────────────────────────────────────────────────
SERP_KEY = os.getenv("SERPAPI_KEY")
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUD_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUD_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not all([SERP_KEY, CLOUD_NAME, CLOUD_KEY, CLOUD_SECRET]):
    raise RuntimeError("SERPAPI_KEY and Cloudinary creds must be set via env vars or .env")

cloudinary.config(  # initialise Cloudinary SDK
    cloud_name=CLOUD_NAME,
    api_key=CLOUD_KEY,
    api_secret=CLOUD_SECRET,
    secure=True,
)

SERP_ENDPOINT = "https://serpapi.com/search.json"
SOCIAL_DOMAINS = [  # lowercase checks
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "linkedin.com",
    "tiktok.com",
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _upload_to_cloudinary(img_bytes: bytes) -> str:
    """Upload bytes; return secure_url suitable for SerpAPI (raw image)."""
    resp = cloudinary.uploader.upload(
        img_bytes,
        folder="missing_finder",
        overwrite=True,
        resource_type="image",
    )
    return resp["secure_url"]


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def search_image(image_bytes: bytes, max_sites: int = 5) -> List[Dict[str, str]]:
    """Reverse image search via Cloudinary + SerpAPI Google Lens."""
    img_url = _upload_to_cloudinary(image_bytes)

    params = {
        "engine": "google_lens",
        "api_key": SERP_KEY,
        "url": img_url,  # SerpAPI expects `url` query param
    }

    resp = requests.get(SERP_ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()
    js = resp.json()

    matches: List[Dict[str, str]] = []
    for item in js.get("visual_matches", []):
        link = item.get("link", "")
        if any(dom in link for dom in SOCIAL_DOMAINS):
            matches.append({"title": item.get("title", link), "url": link})
            if len(matches) >= max_sites:
                break
    return matches


def scrape_profile_title(url: str) -> str:
    """Return a user‑friendly page title for display."""
    try:
        html = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
        og = soup.find("meta", property="og:title")
        return og["content"] if og and og.get("content") else (soup.title.string if soup.title else url)
    except Exception:
        return url
