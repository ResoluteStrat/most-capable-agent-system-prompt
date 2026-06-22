"""Swappable fetcher layer feeding the external-intelligence loop.

A fetcher turns a source (a local feed file, or a URL) into normalized intel items
that `intel.ingest` can score and promote. Two backends ship:
  - FileFetcher: reads a local RSS/Atom/JSON feed — deterministic, offline,
    testable. This is what the eval/tests use.
  - HttpFetcher: urllib over a URL, NETWORK-OPTIONAL — returns [] on any failure
    (graceful degradation) so a missing network never crashes the loop.

Parsing is stdlib (xml.etree). The output item shape matches intel.ingest:
  {source, url, date, category, claim}  (claim = title + summary, so the relevance
  scorer sees the description text).
"""
from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(elem, *names) -> str:
    for child in elem:
        if _local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def _link(elem) -> str:
    for child in elem:
        if _local(child.tag) == "link":
            if child.get("href"):                 # Atom
                return child.get("href")
            if (child.text or "").strip():        # RSS
                return child.text.strip()
    return ""


def parse_feed(text: str) -> list[dict]:
    """RSS 2.0 / RDF / Atom → list of {url, date, category, claim} (no source)."""
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError:
        return []
    items = []
    for el in root.iter():
        kind = _local(el.tag)
        if kind not in ("item", "entry"):
            continue
        title = _text(el, "title")
        summary = _text(el, "description", "summary", "content", "subtitle")
        date = _text(el, "pubdate", "updated", "published", "date")
        claim = (title + (". " + summary if summary else "")).strip()
        if claim:
            items.append({"url": _link(el), "date": date, "category": "feed", "claim": claim})
    return items


def parse_any(text: str) -> list[dict]:
    """Accept a JSON list of items, or an RSS/Atom feed."""
    t = text.strip()
    if t.startswith("[") or t.startswith("{"):
        data = json.loads(t)
        return data if isinstance(data, list) else [data]
    return parse_feed(t)


class FileFetcher:
    def __init__(self, path, source=None):
        self.path = Path(path)
        self.source = source or self.path.stem

    def fetch(self) -> list[dict]:
        items = parse_any(self.path.read_text())
        return [{**i, "source": i.get("source", self.source)} for i in items]


class HttpFetcher:
    def __init__(self, url, source=None, timeout=10):
        self.url = url
        self.source = source or url.split("//")[-1].split("/")[0]
        self.timeout = timeout

    def fetch(self) -> list[dict]:
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout) as r:
                text = r.read().decode("utf-8", "replace")
        except Exception:
            return []                              # network-optional: degrade, don't crash
        return [{**i, "source": i.get("source", self.source)} for i in parse_any(text)]


def make_fetcher(spec, source=None):
    """`spec` is a local path or an http(s) URL."""
    if str(spec).startswith(("http://", "https://")):
        return HttpFetcher(spec, source)
    return FileFetcher(spec, source)


def collect(specs, source=None) -> list[dict]:
    """Run fetchers, dedup by url, return normalized intel items."""
    seen, out = set(), []
    for spec in specs:
        for item in make_fetcher(spec, source).fetch():
            key = item.get("url") or item.get("claim", "")[:60]
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out
