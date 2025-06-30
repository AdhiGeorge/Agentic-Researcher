from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright
import time
from typing import List, Dict
from bs4 import BeautifulSoup
import re
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
import io
import PyPDF2
import os
import random
import json
from src.core.query_sanitizer import sanitize_query
import logging

logger = logging.getLogger(__name__)

class GoogleSearchAPI:
    def __init__(self, api_key, cse_id, max_results=5, timeout=30):
        self.api_key = api_key
        self.cse_id = cse_id
        self.max_results = max_results
        self.timeout = timeout

    def search(self, query):
        url = (
            f"https://www.googleapis.com/customsearch/v1?q={requests.utils.quote(query)}"
            f"&key={self.api_key}&cx={self.cse_id}&num={self.max_results}"
        )
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "body": ""  # No snippet, only URL
                })
            print("[WebSearchService] Used Google Search API fallback for query.")
            return results
        except Exception as e:
            print(f"Google Search API error: {e}")
            return []

class WebSearchService:
    def __init__(self, max_results: int = 5, timeout: int = 30):
        self.max_results = max_results
        self.timeout = timeout
        self.scrape_timeout = 12  # seconds for Playwright scraping
        self.ddgs = DDGS()
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        self.user_agents = [
            # A pool of common user agents
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.google_cse_id = os.getenv('GOOGLE_CSE_ID')
        self.google_search = GoogleSearchAPI(self.google_api_key, self.google_cse_id, self.max_results, self.timeout)
    
    def search_tavily(self, query: str) -> List[Dict]:
        """Search using Tavily API as a fallback."""
        if not self.tavily_api_key:
            logger.warning("Tavily API key not set. Cannot use Tavily fallback.")
            return []
        url = "https://api.tavily.com/search"
        headers = {"Authorization": f"Bearer {self.tavily_api_key}"}
        payload = {"query": query, "max_results": self.max_results}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            # Normalize Tavily results to DuckDuckGo format
            results = []
            for item in data.get('results', []):
                results.append({
                    'title': item.get('title', ''),
                    'link': item.get('url', ''),
                    'body': item.get('content', '')
                })
            logger.info("[WebSearchService] Used Tavily fallback for query.")
            return results
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=10), retry=retry_if_exception_type(Exception))
    def search_duckduckgo(self, query: str) -> List[Dict]:
        """Search using DuckDuckGo with user-agent rotation and retry."""
        try:
            # Rotate user-agent for each search
            user_agent = random.choice(self.user_agents)
            # DDGS does not support user-agent directly, so fallback to requests if needed
            # But we use DDGS for now, and if it fails, fallback to Tavily
            results = list(self.ddgs.text(query, max_results=self.max_results))
            # If results are empty, raise to trigger retry/fallback
            if not results:
                raise Exception("No results from DuckDuckGo.")
            return results
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            raise  # Let tenacity handle the retry

    def search_google(self, query: str) -> List[Dict]:
        if not self.google_api_key or not self.google_cse_id:
            logger.warning("Google API key or CSE ID not set. Cannot use Google fallback.")
            return []
        return self.google_search.search(query)

    def search(self, query: str) -> List[Dict]:
        """Sanitize query, then try DuckDuckGo search, fallback to Tavily, then Google if all retries fail."""
        clean_query = sanitize_query(query)
        if not clean_query:
            logger.warning(f"[WebSearchService] Query sanitized to empty or invalid: '{query}'")
            return []
        try:
            return self.search_duckduckgo(clean_query)
        except Exception as e:
            logger.warning(f"[WebSearchService] DuckDuckGo failed after retries, using Tavily fallback. Error: {e}")
            tavily_results = self.search_tavily(clean_query)
            if tavily_results:
                return tavily_results
            logger.warning("[WebSearchService] Tavily failed, using Google fallback.")
            return self.search_google(clean_query)
    
    def extract_pdf_text(self, url: str) -> str:
        """Download and extract text from a PDF URL using PyPDF2"""
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            with io.BytesIO(response.content) as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                text = "\n".join(page.extract_text() or '' for page in reader.pages)
            # Limit text length
            if len(text) > 5000:
                text = text[:5000] + "..."
            return text
        except Exception as e:
            logger.error(f"PDF extraction error for {url}: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=8), retry=retry_if_exception_type(Exception))
    def scrape_url(self, url: str) -> str:
        """Scrape content from a URL using Playwright or extract PDF if applicable. Returns empty string on failure."""
        # PDF/ArXiv handling
        if url.lower().endswith('.pdf') or 'arxiv.org' in url.lower():
            return self.extract_pdf_text(url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(self.scrape_timeout * 1000)
                
                # Navigate to the page
                page.goto(url)
                
                # Wait for content to load
                page.wait_for_load_state('networkidle')
                
                # Get the page content
                content = page.content()
                
                browser.close()
                
                # Extract text content
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text and clean it
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Limit text length
                if len(text) > 5000:
                    text = text[:5000] + "..."
                
                return text
                
        except Exception as e:
            logger.error(f"[WebSearchService] Scraping error for {url}: {e}")
            return ""  # Never raise, just return empty string
    
    def search_and_scrape(self, query: str) -> List[Dict]:
        """Search for a query, get up to max_results ranked URLs, and scrape them in order. Only use snippets if all scraping fails."""
        search_results = self.search(query)
        urls = [r.get('link', '') for r in search_results if r.get('link', '')][:self.max_results]
        scraped_results = []
        failed_urls = []
        for url in urls:
            if not url:
                continue
            content = self.scrape_url(url)
            if content:
                # Find the original result for title
                result = next((r for r in search_results if r.get('link', '') == url), {})
                scraped_results.append({
                    'title': result.get('title', ''),
                    'url': url,
                    'snippet': '',  # No snippet, only scraped content
                    'content': content
                })
                break  # Stop after first successful scrape
            else:
                failed_urls.append(url)
        # If all scraping failed, fallback to snippets (if any)
        if not scraped_results and search_results:
            logger.warning("[WebSearchService] All scraping failed, using search snippets as fallback.")
            for result in search_results[:self.max_results]:
                scraped_results.append({
                    'title': result.get('title', ''),
                    'url': result.get('link', ''),
                    'snippet': '',
                    'content': result.get('body', '') or 'No content could be scraped.'
                })
        if failed_urls:
            logger.warning(f"[WebSearchService] Failed to scrape URLs: {failed_urls}")
        return scraped_results
    
    def extract_relevant_info(self, scraped_results: List[Dict], query: str) -> str:
        """Extract relevant information from scraped results"""
        if not scraped_results:
            return "No relevant information found."
        
        # Combine all content
        all_content = []
        for result in scraped_results:
            all_content.append(f"Source: {result['title']} ({result['url']})")
            all_content.append(result['content'])
            all_content.append("---")
        
        combined_content = "\n".join(all_content)
        
        # Simple keyword-based relevance scoring
        query_words = set(query.lower().split())
        content_words = set(combined_content.lower().split())
        
        # Calculate relevance score
        relevant_words = query_words.intersection(content_words)
        relevance_score = len(relevant_words) / len(query_words) if query_words else 0
        
        if relevance_score > 0.3:  # Threshold for relevance
            return combined_content
        else:
            return "Content found but may not be highly relevant to the query." 