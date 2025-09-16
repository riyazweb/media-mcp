from __future__ import annotations
import time
import traceback
import requests
import nltk
from bs4 import BeautifulSoup
from ddgs import DDGS
from urllib.parse import urlparse
from typing import List, Dict, Any, Generator
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web_search_scraper", port=8001)

# --- NLTK Setup ---
try:
    nltk.data.find("tokenizers/punkt")
except nltk.downloader.DownloadError:
    print("First-time setup: Downloading NLTK 'punkt' model...")
    nltk.download("punkt")
    nltk.download("punkt_tab")
    print("Download complete.")

# --- Configuration ---
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; MyWebScraper/1.0; +http://mywebsite.com/bot)"
)
DEFAULT_TIMEOUT = 10  # seconds for network requests
MIN_DELAY_BETWEEN_REQUESTS = 1.0  # seconds to wait between requests to the same domain

# --- State Management for Rate Limiting ---
_domain_last_request: Dict[str, float] = {}


# --- Helper Functions ---
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


# --- Agent Tools ---
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


@mcp.tool("extract_relevant_content")
def extract_relevant_content(
    url: str, query: str, max_chars: int = 3000
) -> Dict[str, Any]:
    """
    Scrapes a webpage and extracts the most relevant sentences based on a query.
    This version removes all hyperlink text from the final output.
    """
    print(f"-> Extracting content from '{url}' relevant to '{query}'")
    try:
        _enforce_request_delay(url)
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # --- KEY CHANGE HERE ---
        # Added 'a' to this list to remove all hyperlinks and their text.
        tags_to_remove = [
            "script",
            "style",
            "header",
            "footer",
            "nav",
            "aside",
            "form",
            "a",
        ]
        for element in soup(tags_to_remove):
            element.decompose()

        full_text = " ".join(soup.stripped_strings)
        if not full_text:
            return {"url": url, "content": "No text content found on the page."}

        sentences = nltk.sent_tokenize(full_text)
        query_words = set(word.lower() for word in query.split())

        scored_sentences = []
        for i, sentence in enumerate(sentences):
            sentence_words = set(word.lower() for word in nltk.word_tokenize(sentence))
            score = len(query_words.intersection(sentence_words))
            if score > 0:
                scored_sentences.append((score, i, sentence))

        if not scored_sentences:
            return {
                "url": url,
                "content": (
                    full_text[:max_chars] + "..."
                    if len(full_text) > max_chars
                    else full_text
                ),
            }

        scored_sentences.sort(key=lambda x: x[0], reverse=True)

        final_sentences_to_include = {}
        for score, index, sentence in scored_sentences:
            final_sentences_to_include[index] = sentence
            if index > 0:
                final_sentences_to_include[index - 1] = sentences[index - 1]
            if index < len(sentences) - 1:
                final_sentences_to_include[index + 1] = sentences[index + 1]

        sorted_indices = sorted(final_sentences_to_include.keys())
        final_text = ""
        for index in sorted_indices:
            next_sentence = final_sentences_to_include[index]
            if len(final_text) + len(next_sentence) + 1 > max_chars:
                break
            final_text += next_sentence + " "

        return {"url": url, "content": final_text.strip()}

    except requests.exceptions.RequestException as e:
        return {"error": f"Network error while extracting from {url}: {str(e)}"}
    except Exception as e:
        return {
            "error": f"extract_relevant_content failed for {url}: {str(e)}",
            "trace": traceback.format_exc(),
        }


# --- Test Execution Block ---
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
    # print("--- Running Agent Tool Test with Link Removal ---")

    # user_query = "What are the health benefits of green tea?"
    # print(f"Goal: Answer the question '{user_query}'\n")

    # search_results = search_web(query=user_query)

    # if "error" in search_results or not search_results.get("results"):
    #     print(
    #         f"Error during search: {search_results.get('error', 'No results found.')}"
    #     )
    # else:
    #     top_result = search_results["results"][0]
    #     url_to_scrape = top_result.get("href")
    #     print(f"Found top result: '{top_result.get('title')}'")
    #     print(f"URL: {url_to_scrape}")

    #     if url_to_scrape:
    #         extracted_data = extract_relevant_content(
    #             url=url_to_scrape, query=user_query
    #         )

    #         if "error" in extracted_data:
    #             print(f"\nError during extraction: {extracted_data['error']}")
    #         else:
    #             print("\n--- Extracted Relevant Content (Links Removed) ---")
    #             print(extracted_data.get("content"))
    #             print("\n-------------------------------------------------")
