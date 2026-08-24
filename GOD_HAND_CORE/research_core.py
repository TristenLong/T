import concurrent.futures
import re

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


def search(query, max_results=3):
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except: return []

def scrape_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200: return f"Error: {resp.status_code}"
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "iframe"]):
            script.decompose()
            
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:4000]
    except Exception as e:
        return f"Scrape Error: {str(e)}"

def deep_research(query):
    results = search(query, max_results=3)
    if not results: return "No results."
    
    report = [f"RESEARCH TOPIC: {query}\n"]
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_url = {executor.submit(scrape_url, r['href']): r for r in results}
        for future in concurrent.futures.as_completed(future_to_url):
            r = future_to_url[future]
            try:
                data = future.result()
                report.append(f"### SOURCE: {r['title']}\nURL: {r['href']}\nDATA: {data}\n")
            except: pass
                
    return "\n".join(report)
