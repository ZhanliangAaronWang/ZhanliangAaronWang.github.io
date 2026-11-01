"""Refresh scholar.json from the public Scholar profile.

Use explicit HTTP timeouts instead of scholarly's unbounded CAPTCHA/proxy retries.
On any failed or incomplete fetch, preserve the existing data and fail clearly.
"""
import datetime
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

AUTHOR_ID = "JcKrT8bjRdcC"
OUT = pathlib.Path(__file__).resolve().parent.parent / "scholar.json"
PROFILE = "https://scholar.google.com/citations"


def norm(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:70]


def number(text):
    text = text.strip().replace(",", "").replace("\u00a0", "")
    if text in ("", "–", "-"):
        return 0
    if not text.isdecimal():
        raise ValueError("Unexpected citation count: " + repr(text))
    return int(text)


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#gsc_rsb_st")
    rows = soup.select("tr.gsc_a_tr")
    if table is None or not rows:
        raise RuntimeError("Scholar returned no profile statistics/publications (blocked, CAPTCHA, or changed HTML).")
    stats = []
    for row in table.select("tr"):
        cells = row.select("td.gsc_rsb_std")
        if cells:
            stats.append(number(cells[0].get_text()))
    if len(stats) != 3:
        raise RuntimeError("Expected citations, h-index and i10-index; refusing incomplete data.")
    papers = {}
    for row in rows:
        title = row.select_one("a.gsc_a_at")
        count = row.select_one("a.gsc_a_ac")
        if title is None or count is None:
            raise RuntimeError("Incomplete publication row; existing data will be preserved.")
        papers[norm(title.get_text())] = number(count.get_text())
    more = soup.select_one("#gsc_bpf_more")
    has_more = more is not None and not more.has_attr("disabled")
    return stats, papers, has_more


def download(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AcademicProfileStats/1.0)",
        "Accept-Language": "en-US,en;q=0.9",
    })
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise RuntimeError(
                    f"Google Scholar blocked this runner (HTTP {exc.code}). "
                    "Use a trusted local runner or a configured Scholar API service; "
                    "repeated retries will not resolve an access block."
                ) from exc
            if attempt:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt:
                raise
        time.sleep(2)


def refresh(out=OUT, fetch_html=download):
    papers = {}
    stats = None
    for start in range(0, 1000, 100):
        query = urllib.parse.urlencode({
            "user": AUTHOR_ID, "hl": "en", "cstart": start, "pagesize": 100,
            "sortby": "pubdate",
        })
        print(f"Reading Scholar publications {start + 1}–{start + 100}", flush=True)
        page_stats, page_papers, more = parse_page(fetch_html(PROFILE + "?" + query))
        if stats is not None and stats != page_stats:
            raise RuntimeError("Profile changed during pagination; retry on the next run.")
        stats = page_stats
        papers.update(page_papers)
        if not more:
            break
    else:
        raise RuntimeError("Publication pagination exceeded limit; refusing partial data.")
    data = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "source": "Google Scholar",
        "citations": stats[0], "h_index": stats[1], "i10_index": stats[2],
        "papers": papers,
    }
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(out)
    print(f"Wrote {len(papers)} papers, {stats[0]} citations, h-index {stats[1]}", flush=True)


if __name__ == "__main__":
    try:
        refresh()
    except Exception as exc:
        print(f"::error::Scholar update failed: {type(exc).__name__}: {exc}. Existing scholar.json preserved.", file=sys.stderr)
        sys.exit(1)
