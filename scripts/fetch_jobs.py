import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

JUNK_TITLE_PATTERNS = [
    r"\{\{.*?\}\}",
    r"\|\s*translate",
    r"\b(about\s*us|home|photo\s*gallery|events?\s*gallery|media\s*section|media\s*coverage)\b",
    r"\b(whatsapp\s*channel|privacy\s*policy|terms?\s*(&|and)?\s*conditions?|disclaimer|copyright\s*policy)\b",
    r"\b(screen\s*access|rti|tenders?|governing\s*body|organisation\s*structure|citizens?\s*charter)\b",
    r"\b(debarred|disposed\s*representation|how\s*to\s*reach|contact\s*us|helpdesk|feedback)\b",
    r"dissertation-writingservice\.com",
    r"^icon-",
]

OLD_YEAR_RE = re.compile(r"\b(201[0-9]|202[0-4])\b")
DROP_QUERY_KEYS = {"appid", "enc", "sid", "token", "utm_source", "utm_medium", "utm_campaign"}


def normalize_link(link: str) -> str:
    parsed = urlparse(link.strip())
    filtered_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in DROP_QUERY_KEYS
    ]
    return urlunparse((
        parsed.scheme.lower() or "https",
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        urlencode(filtered_query),
        "",
    ))


def is_valid_item(item: dict) -> bool:
    title = (item.get("title") or "").strip()
    link = (item.get("link") or "").strip()
    if len(title) < 4 or not link.startswith(("http://", "https://")):
        return False

    low_title = title.lower()
    for pat in JUNK_TITLE_PATTERNS:
        if re.search(pat, low_title, flags=re.IGNORECASE):
            return False

    # 2010–2024 ke purane notices filter karein (agar title mein explicit naya year na ho)
    if OLD_YEAR_RE.search(low_title) and not re.search(r"\b(2025|2026|2027)\b", low_title):
        return False

    return True


def make_id(source: str, title: str, clean_link: str) -> str:
    raw = f"{source.strip()}|{title.strip()}|{clean_link.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def save_jobs_json(path: str, raw_items: list[dict]) -> dict:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M+00:00")
    seen_ids = set()
    cleaned_items = []

    for item in raw_items:
        if not is_valid_item(item):
            continue
        clean_link = normalize_link(item["link"])
        source = (item.get("source") or "").strip()
        title = re.sub(r"\s+", " ", (item.get("title") or "").strip())
        item_id = make_id(source, title, clean_link)

        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        cleaned_items.append({
            "id": item_id,
            "title": title,
            "link": clean_link,
            "source": source,
            "category": (item.get("category") or "Update").strip(),
            "official": bool(item.get("official", True)),
            "time": item.get("time") or now_iso,
        })

    payload = {
        "updated": now_iso,
        "items": cleaned_items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return payload
