import concurrent.futures
import re
import time

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# Generic aggregator homepages that pollute results for any broad query. Their
# title/body match these regardless of what was asked.
_HOMEPAGE_PATTERNS = re.compile(
    r'breaking news|latest news headlines|just in|news today|'
    r'world news|see all|live updates|'
    r'view the latest|current events',
    re.IGNORECASE,
)

_TECH_DOMAINS = re.compile(
    r'technologyreview|techcrunch|theverge|arstechnica|wired|nature\.com|'
    r'science|spectrum\.ieee|venturebeat|engadget|gizmodo|zdnet|'
    r'endgadget|quantamagazine|newscientist|sciencedaily|interestingengineering|'
    r'mit|stanford|harvard|openai|googleresearch|deepmind|nature',
    re.IGNORECASE,
)

_MIN_REQUEST_GAP = 10  # seconds between DDGS calls (rate-limit breathing room)
_last_request = 0.0


def _throttle():
    global _last_request
    wait = _MIN_REQUEST_GAP - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()


def _record_failure(source, error):
    try:
        import error_learning
        error_learning.record_error(source, error, context='ddgs_search')
    except Exception:
        pass


def _news(query, max_results):
    """DuckDuckGo news backend: dated article full URLs (best for breakthroughs)."""
    with DDGS() as ddgs:
        return list(ddgs.news(query, max_results=max_results))


def _text(query, max_results):
    """DuckDuckGo text backend: general web results."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search(query, max_results=3, retries=3):
    """News-first search with text fallback. Records failures so the system learns."""
    last_err = None
    for attempt in range(retries):
        try:
            _throttle()
            results = _news(query, max_results=max_results)
            if results:
                return results
        except Exception as e:
            last_err = f"news backend: {e}"
        try:
            _throttle()
            results = _text(query, max_results=max_results)
            if results:
                return results
        except Exception as e:
            last_err = f"text backend: {e}"
        if attempt < retries - 1:
            time.sleep((2 ** attempt) + 0.5)
    _record_failure('duckduckgo_search', last_err or 'DDGS returned empty result set')
    return []


def scrape_url(url):
    headers_default = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    headers_polite = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    for attempt, headers in enumerate((headers_default, headers_polite), 1):
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                for script in soup(["script", "style", "nav", "footer", "header", "iframe"]):
                    script.decompose()
                text = soup.get_text(separator=' ')
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:4000]
            if resp.status_code != 403 and attempt == 1:
                return f"Error: {resp.status_code}"
        except Exception as e:
            if attempt == 2:
                return f"Scrape Error: {str(e)}"
    return "Error: blocked"


def _is_homepage(r):
    text = f"{r.get('title', '')} {r.get('body', '')}"
    return bool(_HOMEPAGE_PATTERNS.search(text))


def _score(r):
    """Rank tech-specific articles above generic news."""
    text = f"{r.get('title', '')} {r.get('body', '')}".lower()
    s = 0
    if _TECH_DOMAINS.search(text):
        s += 2
    if any(k in text for k in ('ai', 'quantum', 'chip', 'robotic', 'fusion',
                               'biotech', 'gene', 'space', 'neuromorphic',
                               'breakthrough', 'scientists', 'researchers')):
        s += 1
    return s


def deep_research(query, max_results=3):
    """News-first research. Homepages filtered out unless nothing else remains."""
    results = []
    seen_domains = set()

    for v in _query_variants(query):
        for r in search(v, max_results=max_results):
            domain = _domain(r.get('url') or r.get('href', ''))
            if not _is_homepage(r):
                if domain and domain in seen_domains:
                    continue
                seen_domains.add(domain)
                results.append(r)

    # If everything got filtered away, fall back to text search (homepages
    # allowed but scored low) so a broad query still yields something useful.
    if not results:
        for v in _query_variants(query):
            for r in search(v, max_results=max_results, retries=1):
                if _score(r) >= 1:
                    results.append(r)

    if not results:
        return "No results. DDGS may be rate-limited; try the browser_swarm tool instead."

    results.sort(key=_score, reverse=True)

    report = [f"RESEARCH TOPIC: {query}\n"]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_url = {}
        for r in results[:6]:
            url = r.get('url') or r.get('href', '')
            if url:
                future_to_url[executor.submit(scrape_url, url)] = r
        for future in concurrent.futures.as_completed(future_to_url):
            r = future_to_url[future]
            try:
                data = future.result()
                if data.startswith('Error:') or data.startswith('Scrape Error:'):
                    body = r.get('body', '')
                    data = f"[fetch blocked] search snippet: {body[:800]}" if body else data
                report.append(f"### SOURCE: {r.get('title', r.get('headline', ''))}\n"
                              f"URL: {r.get('url') or r.get('href')}\n"
                              f"DATE: {r.get('date', '')}\nDATA: {data}\n")
            except Exception:
                pass

    return "\n".join(report)


def _query_variants(query):
    variants = [query]
    stripped = query.strip().strip('"')
    if stripped and stripped.lower() != query.lower():
        variants.append(stripped)
    if len(query.split()) > 5:
        variants.append(' '.join(query.split()[:4]))
    return variants


def _domain(url):
    m = re.match(r'https?://([^/]+)', url or '')
    return m.group(1).replace('www.', '') if m else ''