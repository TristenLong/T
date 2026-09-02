import asyncio
import os

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from google import genai
from loguru import logger
from openai import OpenAI


class BrowserCore:
    def __init__(self, memory_db=None, api_key=None):
        self.memory_db = memory_db
        self.openai_key = api_key or os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.primary_model = os.getenv("JESTER_PRIMARY_LLM", "gemini-3.1-pro")
        self.openai_model = os.getenv("JESTER_OPENAI_MODEL", "gpt-4o")
        
        self.gemini_client = None
        self.openai_client = None
        if self.gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.warning(f"[BrowserCore] Gemini init failed: {e}")
                
        if self.openai_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_key, base_url=os.getenv("OPENAI_BASE_URL") or None)
            except Exception as e:
                logger.warning(f"[BrowserCore] OpenAI init failed: {e}")

    def fetch_page_content(self, url: str, max_chars: int = 4000) -> str:
        """Fetches and cleans visible text from a URL."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove scripts, styles, metadata
                for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                    s.extract()
                text = soup.get_text(separator=" ", strip=True)
                return text[:max_chars]
            return f"[ERROR: HTTP {resp.status_code}]"
        except Exception as e:
            return f"[FETCH_ERROR: {str(e)}]"

    def search_web(self, query: str, max_results: int = 5) -> list:
        """Performs live web search."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return [{"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")} for r in results]
        except Exception as e:
            logger.error(f"[BrowserCore] Search error: {e}")
            return [{"error": str(e)}]

    async def summarize_findings(self, task: str, raw_data: str) -> str:
        sys_prompt = (
            "You are the NAVIGATOR sub-agent of JESTER V2000 Singularity Swarm. "
            "Analyze the web search and page content to provide a concise, high-value tactical summary."
        )
        prompt = f"Objective: {task}\n\nExtracted Web Data:\n{raw_data}"
        
        if self.gemini_client:
            try:
                resp = self.gemini_client.models.generate_content(
                    model=self.primary_model,
                    contents=[sys_prompt, prompt]
                )
                return resp.text
            except Exception as e:
                logger.warning(f"[BrowserCore] Gemini failed: {e}")

        if self.openai_client:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                return resp.choices[0].message.content
            except Exception as e:
                logger.error(f"[BrowserCore] OpenAI failed: {e}")
                
        return raw_data[:1000]

    async def navigate_and_interact(self, task_description: str) -> str:
        logger.info(f"[BrowserCore] Executing navigation task: {task_description}")
        
        # Determine if task is direct URL or search query
        if task_description.startswith("http://") or task_description.startswith("https://"):
            page_text = self.fetch_page_content(task_description)
            summary = await self.summarize_findings(f"Extract key data from {task_description}", page_text)
            return summary
        else:
            search_results = self.search_web(task_description, max_results=4)
            formatted = "\n---\n".join([f"Title: {r.get('title')}\nURL: {r.get('url')}\nSnippet: {r.get('snippet')}" for r in search_results if 'title' in r])
            
            # Deep dive into top URL if available
            top_url = search_results[0].get("url") if search_results and "url" in search_results[0] else None
            if top_url and top_url.startswith("http"):
                page_text = self.fetch_page_content(top_url, max_chars=2000)
                formatted += f"\n\n[TOP SOURCE EXTRACT]:\n{page_text}"
                
            summary = await self.summarize_findings(task_description, formatted)
            return summary

if __name__ == "__main__":
    core = BrowserCore()
    res = asyncio.run(core.navigate_and_interact("Latest developments in humanoid robotics"))
    print(res)
