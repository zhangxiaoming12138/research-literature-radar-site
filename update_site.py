#!/usr/bin/env python3
"""Incrementally update the public literature radar from OpenAlex.

The repository is intentionally self-contained: no private source repository,
credentials, downloaded PDFs, or conversation data are needed. Existing papers.json
is treated as the cumulative index and new public bibliographic records are merged in.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "papers.json"

QUERIES = [
    ("backscatter_temperature_tag", "RF backscatter batteryless temperature sensor"),
    ("backscatter_temperature_tag", "wirelessly powered backscatter sensor"),
    ("dual_band_rectenna", "dual-band rectenna 2.45 GHz"),
    ("dual_band_rectenna", "868 MHz 2.45 GHz RF energy harvesting"),
    ("polarization_robust_rectenna", "polarization insensitive rectenna"),
    ("polarization_robust_rectenna", "orientation independent RF energy harvesting"),
    ("multiport_dc_combining", "multiport rectenna DC combining"),
    ("multiport_dc_combining", "multi-antenna RF energy harvesting rectifier"),
    ("coupling_and_receive_modes", "mutual coupling receiving rectenna"),
    ("coupling_and_receive_modes", "multiport antenna eigenmode energy harvesting"),
    ("low_power_energy_management", "RF energy harvesting cold start MPPT"),
    ("low_power_energy_management", "wireless powered sensor energy harvesting PMIC"),
    ("rectenna_measurement", "rectenna efficiency measurement"),
    ("rectenna_measurement", "multiport antenna radiation efficiency measurement"),
    ("backscatter_reader_chain", "backscatter transceiver load modulation oscillator"),
    ("backscatter_reader_chain", "temperature sensing backscatter reader"),
]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_doi(value: Any) -> str:
    doi = clean(value).lower()
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)


def key_for(item: dict[str, Any]) -> str:
    doi = normalize_doi(item.get("doi"))
    if doi:
        return "doi:" + doi
    oid = clean(item.get("openalex_id"))
    if oid:
        return "openalex:" + oid.rsplit("/", 1)[-1]
    title = re.sub(r"[^a-z0-9]+", " ", clean(item.get("title")).lower()).strip()
    return "title:" + title


def abstract_from_inverted(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in index.items():
        for pos in indexes or []:
            if isinstance(pos, int):
                positions.append((pos, word))
    return " ".join(word for _, word in sorted(positions))


def request_json(url: str, retries: int = 6) -> dict[str, Any]:
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": "research-literature-radar-site/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt + 1 >= retries:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt + 1 >= retries:
                raise
        time.sleep(delay)
        delay = min(delay * 2, 30)
    raise RuntimeError("request failed")


def openalex_record(work: dict[str, Any], topic: str, now: str) -> dict[str, Any]:
    doi = normalize_doi(work.get("doi"))
    authors = []
    for authorship in work.get("authorships") or []:
        name = clean((authorship.get("author") or {}).get("display_name"))
        if name and name not in authors:
            authors.append(name)
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    pub_date = clean(work.get("publication_date"))
    year = work.get("publication_year")
    item = {
        "title": clean(work.get("display_name") or work.get("title")),
        "authors": authors,
        "year": year,
        "publication_date": pub_date,
        "venue": clean(source.get("display_name")),
        "abstract": abstract_from_inverted(work.get("abstract_inverted_index")),
        "doi": doi,
        "openalex_id": clean(work.get("id")),
        "link": f"https://doi.org/{doi}" if doi else clean(work.get("id")),
        "oa": bool((work.get("open_access") or {}).get("is_oa")),
        "score": 0,
        "classification": "自动发现",
        "eligible": False,
        "tags": [],
        "tag_ids": [],
        "topics": [topic],
        "sources": ["openalex"],
        "first_seen": now,
        "last_seen": now,
    }
    item["key"] = key_for(item)
    return item


def merge(old: dict[str, Any], new: dict[str, Any]) -> bool:
    changed = False
    for field in ("title", "venue", "abstract", "publication_date", "doi", "link"):
        nv = new.get(field)
        ov = old.get(field)
        if nv and (not ov or len(str(nv)) > len(str(ov))):
            old[field] = nv
            changed = True
    if new.get("authors") and len(new["authors"]) > len(old.get("authors") or []):
        old["authors"] = new["authors"]
        changed = True
    if new.get("year") and not old.get("year"):
        old["year"] = new["year"]
        changed = True
    for field in ("topics", "sources"):
        cur = list(old.get(field) or [])
        for value in new.get(field) or []:
            if value not in cur:
                cur.append(value)
                changed = True
        old[field] = cur
    if new.get("oa") and not old.get("oa"):
        old["oa"] = True
        changed = True
    old["last_seen"] = new["last_seen"]
    return changed


def fetch_query(topic: str, query: str, start: date, end: date, max_pages: int) -> list[dict[str, Any]]:
    cursor = "*"
    out: list[dict[str, Any]] = []
    for _ in range(max_pages):
        params = {
            "search": query,
            "filter": f"from_publication_date:{start.isoformat()},to_publication_date:{end.isoformat()}",
            "per-page": "100",
            "cursor": cursor,
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        payload = request_json(url)
        results = payload.get("results") or []
        out.extend(results)
        nxt = clean((payload.get("meta") or {}).get("next_cursor"))
        if not results or not nxt or nxt == cursor:
            break
        cursor = nxt
        time.sleep(1.2)
    print(f"{topic}: {query} -> {len(out)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    by_key = {clean(item.get("key")) or key_for(item): item for item in items if item.get("title")}
    now = datetime.now(timezone.utc).isoformat()
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(1, args.days))
    added = 0
    touched = 0
    errors: list[str] = []

    for topic, query in QUERIES:
        try:
            works = fetch_query(topic, query, start, end, max(1, args.max_pages))
        except Exception as exc:
            errors.append(f"{topic}: {type(exc).__name__}: {exc}")
            print("WARN", errors[-1])
            continue
        for work in works:
            item = openalex_record(work, topic, now)
            if not item["title"]:
                continue
            key = item["key"]
            if key in by_key:
                if merge(by_key[key], item):
                    touched += 1
            else:
                by_key[key] = item
                added += 1

    merged = list(by_key.values())
    merged.sort(key=lambda p: (clean(p.get("publication_date")) or str(p.get("year") or ""), clean(p.get("title"))), reverse=True)
    payload["generated_at"] = now
    payload["total"] = len(merged)
    payload["items"] = merged
    payload["update_status"] = {"window_start": start.isoformat(), "window_end": end.isoformat(), "added": added, "updated": touched, "errors": errors}
    DATA.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"total={len(merged)} added={added} updated={touched} errors={len(errors)}")
    return 0 if len(errors) < len(QUERIES) else 2


if __name__ == "__main__":
    raise SystemExit(main())
