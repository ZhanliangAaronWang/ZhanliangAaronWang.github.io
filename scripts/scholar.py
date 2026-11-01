"""Pull citation counts from Google Scholar and write scholar.json for the homepage.

Runs in GitHub Actions (see .github/workflows/scholar.yml). Google Scholar has no API and
sometimes blocks automated requests; when that happens the script exits without touching
the existing scholar.json so the site keeps showing the last good numbers.
"""
import json, re, sys, datetime, pathlib

AUTHOR_ID = "JcKrT8bjRdcC"
OUT = pathlib.Path(__file__).resolve().parent.parent / "scholar.json"

def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:70]

try:
    from scholarly import scholarly
    author = scholarly.search_author_id(AUTHOR_ID)
    author = scholarly.fill(author, sections=["basics", "indices", "publications"])
except Exception as e:  # blocked, rate limited, network error…
    print("scholar fetch failed:", e, file=sys.stderr)
    sys.exit(0)

papers = {}
for pub in author.get("publications", []):
    title = pub.get("bib", {}).get("title", "")
    if title:
        papers[norm(title)] = int(pub.get("num_citations", 0) or 0)

data = {
    "updated": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
    "source": "Google Scholar",
    "citations": int(author.get("citedby", 0) or 0),
    "h_index": int(author.get("hindex", 0) or 0),
    "i10_index": int(author.get("i10index", 0) or 0),
    "papers": papers,
}
if not papers:
    print("no publications returned; keeping the previous file", file=sys.stderr)
    sys.exit(0)
OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT} with {len(papers)} papers, {data['citations']} citations")
