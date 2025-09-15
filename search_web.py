import time
import traceback
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urlparse, urljoin
import urllib.robotparser
from typing import List, Dict, Any, Iterable, Union
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web_search_scraper", port=8001)

# Configuration
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; MCPWebScraper/1.0)"
DEFAULT_TIMEOUT = 10  # seconds
MIN_DELAY_BETWEEN_REQUESTS = 1.0  # seconds per domain

_domain_last_request: Dict[str, float] = {}


def _safe_sleep_for_domain(url: str) -> None:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    now = time.time()
    last = _domain_last_request.get(domain, 0)
    elapsed = now - last
    if elapsed < MIN_DELAY_BETWEEN_REQUESTS:
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS - elapsed)
    _domain_last_request[domain] = time.time()


def _check_robots(url: str, user_agent: str = "*") -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If we cannot fetch or parse robots.txt, allow with caution (as before).
        # If you prefer a conservative approach, change this to `return False`.
        return True


def _ensure_iterable(obj: Any) -> Iterable:
    """
    Helper: if obj is an iterator/generator, iterate it; if it's a list, return as-is;
    if it's a single item, wrap into list.
    """
    if obj is None:
        return []
    if isinstance(obj, (list, tuple, set)):
        return obj
    try:
        iter(obj)
        return obj
    except TypeError:
        return [obj]


@mcp.tool("search_web")
def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Use DDGS to perform text search.
    Returns up to max_results results as list of {title, href, snippet}.
    """
    try:
        with DDGS(timeout=DEFAULT_TIMEOUT) as ddgs:
            raw = ddgs.text(query=query, max_results=max_results)
            raw = list(_ensure_iterable(raw))
        results: List[Dict[str, str]] = []
        for r in raw:
            if not isinstance(r, dict):
                # Some versions might return string lines; skip those
                continue
            title = r.get("title", "") or ""
            href = r.get("href", "") or r.get("url", "") or ""
            snippet = r.get("body") or r.get("snippet") or r.get("abstract") or ""
            results.append({"title": title, "href": href, "snippet": snippet})
            if len(results) >= max_results:
                break
        return {"results": results}
    except Exception as e:
        return {"error": f"search_web error: {str(e)}", "trace": traceback.format_exc()}


@mcp.tool("search_images")
def search_images(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search images with DDGS. Returns up to max_results image URLs.
    Handles different return types from ddgs.images.
    """
    try:
        with DDGS(timeout=DEFAULT_TIMEOUT) as ddgs:
            image_gen = ddgs.images(query=query)
            images: List[str] = []
            for item in _ensure_iterable(image_gen):
                if len(images) >= max_results:
                    break
                # item might be string URL or dict with various keys
                if isinstance(item, str):
                    images.append(item)
                    continue
                if isinstance(item, dict):
                    url = (
                        item.get("image")
                        or item.get("url")
                        or item.get("src")
                        or item.get("thumbnail")
                    )
                    if isinstance(url, str) and url:
                        images.append(url)
                        continue
                # otherwise ignore item
            return {"images": images}
    except Exception as e:
        return {
            "error": f"search_images error: {str(e)}",
            "trace": traceback.format_exc(),
        }


@mcp.tool("scrape_site")
def scrape_site(url: str, max_chars: int = 2000) -> Dict[str, Any]:
    """
    Scrape visible text content from a static (non-JS) website.
    """
    try:
        if not _check_robots(url, user_agent=DEFAULT_USER_AGENT):
            return {"error": "Disallowed by robots.txt"}

        _safe_sleep_for_domain(url)

        resp = requests.get(
            url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")

        # Remove tags we don't want
        for tag in soup(
            ["script", "style", "noscript", "header", "footer", "nav", "aside"]
        ):
            tag.decompose()

        text = " ".join(soup.stripped_strings)
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return {"url": url, "content": text}
    except Exception as e:
        return {
            "error": f"scrape_site error: {str(e)}",
            "trace": traceback.format_exc(),
        }


@mcp.tool("scrape_links")
def scrape_links(url: str, limit: int = 20) -> Dict[str, Any]:
    """
    Extract links from a page up to a limit.
    """
    try:
        if not _check_robots(url, user_agent=DEFAULT_USER_AGENT):
            return {"error": "Disallowed by robots.txt"}

        _safe_sleep_for_domain(url)

        resp = requests.get(
            url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")
        links: List[Dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True) or ""
            absolute_href = urljoin(url, href)
            links.append({"text": text, "href": absolute_href})
            if len(links) >= limit:
                break

        return {"url": url, "links": links}
    except Exception as e:
        return {
            "error": f"scrape_links error: {str(e)}",
            "trace": traceback.format_exc(),
        }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
