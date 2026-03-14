"""Web crawler connector using crawl4ai."""

import asyncio
from typing import Any

from connectors.base import BaseConnector


class WebCrawlerConnector(BaseConnector):
    """Connector for crawling web pages and converting to markdown.

    Uses crawl4ai to fetch URLs and extract clean markdown content.
    Respects robots.txt by default.
    """

    def __init__(self, max_pages: int = 50, respect_robots: bool = True):
        """Initialize the web crawler connector.

        Args:
            max_pages: Maximum number of pages to crawl per URL
            respect_robots: Whether to respect robots.txt
        """
        self.max_pages = max_pages
        self.respect_robots = respect_robots
        self._crawler = None

    def connect(self) -> None:
        """Initialize the crawler."""
        pass

    def disconnect(self) -> None:
        """Cleanup crawler resources."""
        self._crawler = None

    def fetch(self, source: str) -> dict[str, Any]:
        """Fetch content from a URL.

        Args:
            source: URL to fetch

        Returns:
            Dictionary with keys:
                - content: str - Markdown content
                - file_type: str - Always 'url'
                - url: str - The original URL
                - title: str - Page title if available
                - error: str - Error message if failed
        """
        result = {
            "content": "",
            "file_type": "url",
            "url": source,
            "title": None,
            "error": None,
        }

        # Validate URL
        if not source.startswith(("http://", "https://")):
            result["error"] = (
                f"Invalid URL: {source}. Must start with http:// or https://"
            )
            return result

        try:
            content = asyncio.run(self._fetch_async(source))
            result["content"] = content
        except ImportError as e:
            result["error"] = f"crawl4ai not installed: {e}"
        except Exception as e:
            result["error"] = f"Crawling error: {e}"

        return result

    async def _fetch_async(self, url: str) -> str:
        """Fetch URL asynchronously using crawl4ai."""
        try:
            from crawl4ai import Crawler

            crawler = Crawler()

            result = await crawler.arun(
                url=url,
                max_pages=self.max_pages,
                respect_robots_txt=self.respect_robots,
            )

            if result.success:
                return result.markdown
            else:
                raise ValueError(f"Crawl failed: {result.error}")

        except Exception as e:
            raise ValueError(f"Error crawling {url}: {e}")
