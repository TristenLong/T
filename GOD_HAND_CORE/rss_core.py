import os
import re
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

USER_AGENT = 'JESTER-RSS-AGGREGATOR/1.0 (local voice assistant)'

_TAG_RE = re.compile(r'<[^>]+>')


def _localname(tag):
    return tag.rsplit('}', 1)[-1]


def _resolve_url(query):
    q = (query or '').strip()
    if not q:
        return None
    if q.lower().startswith('http://') or q.lower().startswith('https://'):
        return q
    m = re.match(r'^(?:r/)?([a-zA-Z0-9_]+)$', q, re.IGNORECASE)
    if m:
        return 'https://www.reddit.com/r/{}/.rss'.format(m.group(1))
    return None


def _clean(html_text):
    text = _TAG_RE.sub(' ', html_text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_items(raw):
    root = ElementTree.fromstring(raw)
    items = []
    if _localname(root.tag) == 'feed':
        for entry in root.iter():
            if _localname(entry.tag) != 'entry':
                continue
            link = ''
            for child in entry:
                if _localname(child.tag) == 'link':
                    link = child.get('href') or link
            title = ''
            for child in entry:
                if _localname(child.tag) == 'title':
                    title = (child.text or '')
                    break
            published = ''
            summary = ''
            content = ''
            for child in entry.iter():
                n = _localname(child.tag)
                if n == 'updated' and not published:
                    published = child.text or ''
                elif n == 'summary' and not summary:
                    summary = child.text or ''
                elif n == 'content' and not content:
                    content = child.text or ''
            summary = summary or content
            items.append({'title': title.strip(), 'link': link,
                          'published': published.strip(), 'summary': _clean(summary)})
    else:
        for item in root.iter('item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            desc = item.findtext('description', '')
            pub = item.findtext('pubDate', '')
            items.append({'title': (title or '').strip(), 'link': (link or '').strip(),
                          'published': (pub or '').strip(), 'summary': _clean(desc)})
    return items


def fetch_rss(query, limit=5):
    url = _resolve_url(query)
    if not url:
        return ("ERROR: Could not turn that into an RSS feed. Use a subreddit like 'r/singularity', "
                "a plain subreddit name, or a full feed URL.")
    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=20)
    except requests.RequestException as e:
        return f"ERROR: Could not fetch RSS from {url}: {e}"

    if r.status_code in (401, 403):
        return f"ERROR: {url} refused access (HTTP {r.status_code}). This feed requires auth or blocks this client."
    if r.status_code == 429:
        return f"ERROR: {url} temporarily rate-limited us (HTTP 429). Wait a minute and try again."
    if r.status_code != 200:
        return f"ERROR: RSS fetch failed (HTTP {r.status_code}) for {url}"

    try:
        items = _parse_items(r.content)
    except ElementTree.ParseError:
        return f"ERROR: {url} did not return valid XML/RSS."

    if not items:
        return f"No posts found in feed: {url}"

    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 5

    out = []
    for it in items[:limit]:
        ts = f"[{it['published']}] " if it['published'] else ''
        summary = it['summary'][:400] if it['summary'] else '(no summary)'
        out.append(f"{ts}{it['title']}\nLINK: {it['link']}\nSUMMARY: {summary}")
    return "\n---\n".join(out)


if __name__ == '__main__':
    import sys
    print(fetch_rss(sys.argv[1] if len(sys.argv) > 1 else 'r/singularity'))