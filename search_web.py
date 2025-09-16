from __future__ import annotations
import time
import traceback
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urlparse
from typing import List, Dict, Any, Generator

# MCP Server Setup (placeholder for demonstration)
class McpToolPlaceholder:
    def tool(self, name):
        def decorator(func):
            return func

        return decorator


mcp = McpToolPlaceholder()

# --- Configuration ---
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; MyWebScraper/1.0; +http://mywebsite.com/bot)"
)
DEFAULT_TIMEOUT = 10  # seconds for network requests
MIN_DELAY_BETWEEN_REQUESTS = 1.0  # seconds to wait between requests to the same domain

# --- State Management for Rate Limiting ---
_domain_last_request: Dict[str, float] = {}


def _get_domain(url: str) -> str | None:
    """Extracts the network location (domain) from a URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def _enforce_request_delay(url: str) -> None:
    """Waits if necessary to respect MIN_DELAY_BETWEEN_REQUESTS for a domain."""
    domain = _get_domain(url)
    if not domain:
        return

    now = time.time()
    last_request_time = _domain_last_request.get(domain, 0)
    elapsed = now - last_request_time

    if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS - elapsed)

    _domain_last_request[domain] = time.time()


@mcp.tool("search_web")
def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Performs a web search using DuckDuckGo and returns the results.
    """
    print(f"-> Searching for: '{query}'")
    try:
        results_generator: Generator[Dict[str, str], None, None] = DDGS(
            timeout=DEFAULT_TIMEOUT
        ).text(query=query, max_results=max_results)

        results = [
            {
                "title": r.get("title", ""),
                "href": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results_generator
        ]

        return {"results": results}
    except Exception as e:
        return {
            "error": f"search_web failed: {str(e)}",
            "trace": traceback.format_exc(),
        }


@mcp.tool("scrape_site_content")
def scrape_site_content(url: str, max_chars: int = 4000) -> Dict[str, Any]:
    """
    Scrapes the visible text content from a single webpage.
    """
    print(f"-> Scraping content from: '{url}'")
    try:
        # The robots.txt check that was here has been REMOVED.

        _enforce_request_delay(url)

        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(
            ["script", "style", "header", "footer", "nav", "aside", "form"]
        ):
            element.decompose()

        text = " ".join(soup.stripped_strings)

        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return {"url": url, "content": text}

    except requests.exceptions.RequestException as e:
        return {"error": f"Network error while scraping {url}: {str(e)}"}
    except Exception as e:
        return {
            "error": f"scrape_site_content failed for {url}: {str(e)}",
            "trace": traceback.format_exc(),
        }


if __name__ == "__main__":
    print("--- Testing Web Search ---")
    search_results = search_web(query="latest advancements in AI")
    if "error" in search_results:
        print(f"Error during search: {search_results['error']}")
    elif search_results["results"]:
        first_result = search_results["results"][0]
        print(f"Search successful. Found {len(search_results['results'])} results.")
        print(f"Top result: '{first_result['title']}' - {first_result['href']}")

        print("\n--- Testing Scraper (robots.txt ignored) ---")
        scrape_url = first_result.get("href")
        if scrape_url:
            scraped_data = scrape_site_content(scrape_url)
            if "error" in scraped_data:
                print(f"Error during scraping: {scraped_data['error']}")
            else:
                print(f"Successfully scraped content from {scrape_url}:")
                print("-" * 20)
                print(scraped_data.get("content", "No content found."))
                print("-" * 20)
    else:
        print("Search returned no results.")
