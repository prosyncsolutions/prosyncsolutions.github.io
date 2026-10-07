"""Technical SEO crawler: crawls a site from its home page and reports on-page and technical issues.

Usage:  py seo_crawler.py https://example.com [--max-pages 500] [--out results]
Writes: <out>/pages.csv (one row per URL) and <out>/findings.json (issues grouped by check).
Python standard library only.
"""

import argparse
import csv
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import defaultdict
from html.parser import HTMLParser

UA = "ProsyncSEOAudit/1.0"
TITLE_MAX, DESC_MIN, DESC_MAX, THIN_WORDS, HEAVY_IMG = 60, 70, 160, 300, 300_000


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.meta, self.links, self.imgs = "", {}, [], []
        self.h1, self.canonical, self.lang = [], None, None
        self._in_title = self._in_h1 = self._skip = False
        self._text = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name"):
            self.meta[a["name"].lower()] = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img":
            self.imgs.append({"src": a.get("src", ""), "alt": a.get("alt")})
        elif tag == "h1":
            self._in_h1 = True
            self.h1.append("")
        elif tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1 and self.h1:
            self.h1[-1] += data
        if not self._skip and not self._in_title:
            self._text.append(data)

    @property
    def word_count(self):
        return len(re.findall(r"[A-Za-z0-9'’-]+", " ".join(self._text)))


def fetch(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read() if method == "GET" else b""
            return r.status, r.headers, body, r.geturl(), time.perf_counter() - start
    except urllib.error.HTTPError as e:
        return e.code, e.headers, b"", url, time.perf_counter() - start
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, {}, str(e).encode(), url, time.perf_counter() - start


def normalise(url):
    p = urllib.parse.urlsplit(url)
    path = p.path or "/"
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), path, p.query, ""))


def crawl(start, max_pages):
    root = urllib.parse.urlsplit(start)
    host = root.netloc.lower()
    pages, inlinks, link_sources = {}, defaultdict(set), defaultdict(set)
    queue, seen = [normalise(start)], {normalise(start)}
    img_cache = {}

    robots = urllib.robotparser.RobotFileParser()
    r_status, _, r_body, _, _ = fetch(f"{root.scheme}://{host}/robots.txt")
    robots.parse(r_body.decode("utf-8", "replace").splitlines() if r_status == 200 else [])
    sitemap_urls = []
    s_status, _, s_body, _, _ = fetch(f"{root.scheme}://{host}/sitemap.xml")
    if s_status == 200:
        sitemap_urls = [normalise(u) for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", s_body.decode("utf-8", "replace"))]

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        status, headers, body, final, secs = fetch(url)
        page = {"url": url, "status": status, "seconds": round(secs, 3), "bytes": len(body),
                "blocked_by_robots": not robots.can_fetch(UA, url)}
        pages[url] = page
        ctype = headers.get("Content-Type", "") if headers else ""
        if status != 200 or "html" not in ctype:
            continue
        p = PageParser()
        p.feed(body.decode("utf-8", "replace"))
        page.update({
            "title": p.title.strip(), "meta_description": p.meta.get("description"),
            "robots_meta": p.meta.get("robots", ""), "viewport": "viewport" in p.meta,
            "lang": p.lang, "h1": [h.strip() for h in p.h1], "canonical": p.canonical,
            "word_count": p.word_count, "images": [],
        })
        for img in p.imgs:
            src = urllib.parse.urljoin(url, img["src"])
            if src not in img_cache:
                st, h, b, _, _ = fetch(src)
                img_cache[src] = (st, len(b))
            page["images"].append({"src": src, "alt": img["alt"], "status": img_cache[src][0], "bytes": img_cache[src][1]})
        for href in p.links:
            target = urllib.parse.urljoin(url, href)
            if urllib.parse.urlsplit(target).scheme not in ("http", "https"):
                continue
            target = normalise(target)
            if urllib.parse.urlsplit(target).netloc.lower() != host:
                continue
            inlinks[target].add(url)
            link_sources[target].add(url)
            if target not in seen:
                seen.add(target)
                queue.append(target)

    # Sitemap URLs that the crawl never reached through links
    for u in sitemap_urls:
        if u not in pages:
            status, headers, body, _, secs = fetch(u)
            pages[u] = {"url": u, "status": status, "seconds": round(secs, 3), "bytes": len(body),
                        "blocked_by_robots": not robots.can_fetch(UA, u), "found_via": "sitemap only"}
            if status == 200 and "html" in (headers.get("Content-Type", "") if headers else ""):
                p = PageParser()
                p.feed(body.decode("utf-8", "replace"))
                pages[u].update({"title": p.title.strip(), "meta_description": p.meta.get("description"),
                                 "robots_meta": p.meta.get("robots", ""), "word_count": p.word_count,
                                 "h1": [h.strip() for h in p.h1], "canonical": p.canonical,
                                 "viewport": "viewport" in p.meta, "lang": p.lang, "images": []})
    return pages, inlinks, link_sources, sitemap_urls, r_status, s_status


def analyse(pages, inlinks, link_sources, sitemap_urls, robots_status, sitemap_status, start):
    f = defaultdict(list)
    html_pages = {u: p for u, p in pages.items() if "title" in p}
    home = normalise(start)

    for u, p in pages.items():
        if p["status"] != 200:
            f["broken_internal_url"].append({"url": u, "status": p["status"], "linked_from": sorted(link_sources.get(u, []))})
        if p.get("blocked_by_robots") and (u in inlinks or u in sitemap_urls):
            f["blocked_by_robots_txt"].append({"url": u})

    by_title, by_desc = defaultdict(list), defaultdict(list)
    for u, p in html_pages.items():
        t, d = p["title"], p.get("meta_description")
        if not t:
            f["missing_title"].append({"url": u})
        else:
            by_title[t].append(u)
            if len(t) > TITLE_MAX:
                f["title_too_long"].append({"url": u, "length": len(t), "title": t})
        if not d:
            f["missing_meta_description"].append({"url": u})
        else:
            by_desc[d].append(u)
            if not DESC_MIN <= len(d) <= DESC_MAX:
                f["meta_description_length"].append({"url": u, "length": len(d)})
        if len(p["h1"]) == 0:
            f["missing_h1"].append({"url": u})
        elif len(p["h1"]) > 1:
            f["multiple_h1"].append({"url": u, "h1": p["h1"]})
        if p["word_count"] < THIN_WORDS:
            f["thin_content"].append({"url": u, "words": p["word_count"]})
        if "noindex" in p["robots_meta"].lower() and u in sitemap_urls:
            f["noindex_page_in_sitemap"].append({"url": u})
        if p["canonical"]:
            canon = normalise(urllib.parse.urljoin(u, p["canonical"]))
            if canon != u:
                f["canonical_points_elsewhere"].append({"url": u, "canonical": canon})
        else:
            f["missing_canonical"].append({"url": u})
        if not p["viewport"]:
            f["missing_viewport"].append({"url": u})
        if not p["lang"]:
            f["missing_lang"].append({"url": u})
        for img in p.get("images", []):
            if img["alt"] is None:
                f["image_missing_alt"].append({"url": u, "image": img["src"]})
            if img["status"] != 200:
                f["broken_image"].append({"url": u, "image": img["src"], "status": img["status"]})
            elif img["bytes"] > HEAVY_IMG:
                f["heavy_image"].append({"url": u, "image": img["src"], "kb": img["bytes"] // 1024})
        if u != home and u not in inlinks:
            f["orphan_page"].append({"url": u, "note": "in sitemap but no internal links point to it"})

    for t, urls in by_title.items():
        if len(urls) > 1:
            f["duplicate_title"].append({"title": t, "urls": urls})
    for d, urls in by_desc.items():
        if len(urls) > 1:
            f["duplicate_meta_description"].append({"description": d[:80] + "…", "urls": urls})

    crawled_ok = [u for u, p in html_pages.items() if p["status"] == 200 and "noindex" not in p["robots_meta"].lower()]
    if sitemap_status != 200:
        f["sitemap_missing"].append({"status": sitemap_status})
    else:
        for u in sitemap_urls:
            if pages.get(u, {}).get("status") != 200:
                f["sitemap_lists_broken_url"].append({"url": u, "status": pages.get(u, {}).get("status")})
        for u in crawled_ok:
            if u not in sitemap_urls:
                f["indexable_page_missing_from_sitemap"].append({"url": u})
    if robots_status != 200:
        f["robots_txt_missing"].append({"status": robots_status})
    return dict(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("--max-pages", type=int, default=500)
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(exist_ok=True)

    pages, inlinks, link_sources, sitemap_urls, rs, ss = crawl(a.start, a.max_pages)
    findings = analyse(pages, inlinks, link_sources, sitemap_urls, rs, ss, a.start)

    with open(out / "pages.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["url", "status", "title", "title_len", "meta_description_len", "h1_count", "words", "canonical", "robots_meta", "inlinks", "seconds"])
        for u, p in sorted(pages.items()):
            w.writerow([u, p["status"], p.get("title", ""), len(p.get("title", "")), len(p.get("meta_description") or ""),
                        len(p.get("h1", [])), p.get("word_count", ""), p.get("canonical", ""), p.get("robots_meta", ""),
                        len(inlinks.get(u, [])), p["seconds"]])
    summary = {"start": a.start, "urls_checked": len(pages), "html_pages": sum(1 for p in pages.values() if "title" in p),
               "sitemap_urls": len(sitemap_urls), "issue_types": len(findings),
               "issue_instances": sum(len(v) for v in findings.values())}
    (out / "findings.json").write_text(json.dumps({"summary": summary, "findings": findings}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for k, v in sorted(findings.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(v):>3}  {k}")


if __name__ == "__main__":
    main()
