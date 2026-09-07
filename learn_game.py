"""Search-learning: researches a game's controls / how-to-play and returns
driver hints (start keys, win markers, death markers, strategy) so web_agent.mjs
can play unfamiliar games. Pure offline CLI: reads game name from argv, prints JSON."""
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
    HAVE_DDGS = True
except Exception:
    HAVE_DDGS = False

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def search_text(query, max_results=5):
    """Search using ddgs (primary) then DuckDuckGo html as fallback."""
    hits = []
    if HAVE_DDGS:
        try:
            with DDGS() as d:
                for r in d.text(query, max_results=max_results, region="wt-wt", safe="off"):
                    hits.append((r.get("title", ""), r.get("href", ""), r.get("body", "")))
            if hits:
                return hits
        except Exception:
            pass
    try:
        url = "https://html.duckduckgo.com/html/"
        resp = requests.get(url, params={"q": query}, headers={"User-Agent": UA}, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for r in soup.select("div.result")[:max_results]:
                a = r.select_one("a.result__a")
                s = r.select_one("a.result__snippet")
                if a:
                    hits.append((a.get_text(" ", strip=True), a.get("href", ""), s.get_text(" ", strip=True) if s else ""))
    except Exception:
        pass
    return hits


def fetch_page(url, max_chars=6000):
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text)[:max_chars]
    except Exception:
        return ""


def parse_controls(text):
    if not text:
        return {}
    low = text.lower()
    hints = {}
    if re.search(r"\b(select|insert coin|start button)\b", low):
        hints["start_keys"] = hints.get("start_keys", [])
        for k, lbl in (("x", "b button"), ("z", "a button"), ("enter", "start"), ("1", "1 player"), ("5", "coin")):
            if lbl in low:
                hints["start_keys"].append(k)
    if re.search(r"\b(dig|pump)\b", low):
        hints["strategy"] = "dig-dug"
    if re.search(r"\broad\b", low) and re.search(r"enem", low):
        hints["note"] = "round-based; win when ROUND n increments to 2"
    for pat in (r"round\s*2", r"level\s*2", r"stage\s*2", r"world\s*2"):
        if re.search(pat, low):
            hints["win"] = pat.replace("\\s*", " ")
    if re.search(r"game\s*over", low):
        hints["dead"] = "GAME OVER"
    return hints


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else "dig dug"
    out = {
        "game": game,
        "query": f"{game} controls how to play walkthrough",
        "sources": [],
        "text": "",
        "hints": {},
    }
    try:
        hits = search_text(out["query"])
        for title, url, body in hits[:4]:
            out["sources"].append({"title": title, "url": url, "snippet": body[:240]})
            if not out["text"] and ("controls" in body.lower() or "how to play" in body.lower()):
                txt = fetch_page(url)
                if txt:
                    out["text"] = txt[:2500]
                    break
        if not out["text"] and out["sources"]:
            txt = fetch_page(out["sources"][0]["url"])
            out["text"] = txt[:2500]
        out["hints"] = parse_controls(out["text"] or " ".join(s["snippet"] for s in out["sources"]))
    except Exception as e:
        out["error"] = str(e)
    print(json.dumps(out))


if __name__ == "__main__":
    main()