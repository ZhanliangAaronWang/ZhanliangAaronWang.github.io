"""Pull citation counts from Google Scholar and write scholar.json for the homepage.

Runs in GitHub Actions (see .github/workflows/scholar.yml) or on your own machine:

    pip install scholarly
    python scripts/scholar.py

Google Scholar has no API and often blocks requests from data-centre IPs such as GitHub's
runners. The script tries a direct connection first, then rotates through free proxies.
If every attempt fails it exits with an error (so the Actions run shows red) and leaves
the existing scholar.json untouched, so the site keeps showing the last good numbers.
"""
import json, re, sys, datetime, pathlib

AUTHOR_ID = "JcKrT8bjRdcC"
OUT = pathlib.Path(__file__).resolve().parent.parent / "scholar.json"


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:70]


def fetch(use_proxy: bool):
    from scholarly import scholarly, ProxyGenerator
    if use_proxy:
        pg = ProxyGenerator()
        if not pg.FreeProxies():
            raise RuntimeError("could not set up a free proxy")
        scholarly.use_proxy(pg)
    author = scholarly.search_author_id(AUTHOR_ID)
    return scholarly.fill(author, sections=["basics", "indices", "publications"])


author = None
for attempt, use_proxy in enumerate([False, True, True], start=1):
    try:
        print(f"attempt {attempt}: {'proxy' if use_proxy else 'direct'}", flush=True)
        author = fetch(use_proxy)
        if author and author.get("publications"):
            break
        print("  no publications returned", flush=True)
    except Exception as e:  # blocked, captcha, rate limit, network error…
        print(f"  failed: {type(e).__name__}: {e}", flush=True)
        author = None

if not author or not author.get("publications"):
    print("Google Scholar could not be read from this network; scholar.json left unchanged.", file=sys.stderr)
    sys.exit(1)

papers = {}
for pub in author["publications"]:
    title = pub.get("bib", {}).get("title", "")
    if title:
        papers[norm(title)] = int(pub.get("num_citations", 0) or 0)

data = {
    "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    "source": "Google Scholar",
    "citations": int(author.get("citedby", 0) or 0),
    "h_index": int(author.get("hindex", 0) or 0),
    "i10_index": int(author.get("i10index", 0) or 0),
    "papers": papers,
}
OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT}: {len(papers)} papers, {data['citations']} citations, h-index {data['h_index']}")
