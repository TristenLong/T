import logging
import re

import requests
from bs4 import BeautifulSoup
import llm_router

logger = logging.getLogger("CRAWLER_AGENT")
logger.setLevel(logging.INFO)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def fetch_url_text(url):
    """
    Fetches the raw HTML of a URL, strips scripts/styles, and returns clean text.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        logger.info(f"Crawling URL: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Remove script, style, meta, and noscript tags
        for element in soup(["script", "style", "meta", "noscript"]):
            element.decompose()
            
        # Extract text and collapse whitespace
        text = soup.get_text(separator=' ')
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        return clean_text
    except Exception as e:
        logger.error(f"Failed to crawl {url}: {e}")
        return f"Error crawling {url}: {e}"

def crawl_and_summarize(url, max_chars=10000):
    """
    Crawls a URL and uses the LLM to summarize and extract meaning if it exceeds the chunk limit.
    """
    text = fetch_url_text(url)
    
    if len(text) <= max_chars:
        return text
        
    logger.info(f"Extracted text too long ({len(text)} chars). Initiating LLM summarization chunks.")
    
    chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
    summaries = []
    
    for i, chunk in enumerate(chunks[:5]): # Limit to 5 chunks
        prompt = f"Summarize the following extracted web content. Focus on the core facts, data, and findings:\n\n{chunk}"
        messages = [{"role": "user", "content": prompt}]
        try:
            summary = llm_router.generate_completion(messages)
            summaries.append(f"--- Chunk {i+1} Summary ---\n{summary}")
        except Exception as e:
            logger.error(f"Summarization failed for chunk {i}: {e}")
            summaries.append(f"--- Chunk {i+1} (Truncated) ---\n{chunk[:1000]}...")
            
    final_text = "\n\n".join(summaries)
    return final_text

if __name__ == "__main__":
    # Test crawler
    print(crawl_and_summarize("https://en.wikipedia.org/wiki/Singularity"))
