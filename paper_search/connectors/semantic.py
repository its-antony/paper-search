# paper_search/connectors/semantic.py
from typing import List, Optional
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import time
import random
from ..models.paper import Paper
from ..utils import extract_doi
from .base import PaperConnector, ConnectorCapabilities
from .registry import register
import logging
from PyPDF2 import PdfReader
import re
from ..config import get_env

logger = logging.getLogger(__name__)


@register("semantic")
class SemanticConnector(PaperConnector):
    """Semantic Scholar paper search implementation"""

    capabilities = ConnectorCapabilities(search=True, download=True, read=True)

    SEMANTIC_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    SEMANTIC_BASE_URL = "https://api.semanticscholar.org/graph/v1"
    BROWSERS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]

    def __init__(self):
        self._setup_session()

    def _setup_session(self):
        """Initialize session with random user agent"""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": random.choice(self.BROWSERS),
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from Semantic Scholar format (e.g., '2025-06-02')"""
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None

    def _extract_url_from_disclaimer(self, disclaimer: str) -> str:
        """Extract URL from disclaimer text"""
        url_patterns = [
            r'https?://[^\s,)]+',
            r'https?://arxiv\.org/abs/[^\s,)]+',
            r'https?://[^\s,)]*\.pdf',
        ]

        all_urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, disclaimer)
            all_urls.extend(matches)

        if not all_urls:
            return ""

        doi_urls = [url for url in all_urls if 'doi.org' in url]
        if doi_urls:
            return doi_urls[0]

        non_unpaywall_urls = [url for url in all_urls if 'unpaywall.org' not in url]
        if non_unpaywall_urls:
            url = non_unpaywall_urls[0]
            if 'arxiv.org/abs/' in url:
                pdf_url = url.replace('/abs/', '/pdf/')
                return pdf_url
            return url

        if all_urls:
            url = all_urls[0]
            if 'arxiv.org/abs/' in url:
                pdf_url = url.replace('/abs/', '/pdf/')
                return pdf_url
            return url

        return ""

    def _parse_paper(self, item) -> Optional[Paper]:
        """Parse single paper entry from Semantic Scholar HTML and optionally fetch detailed info"""
        try:
            if not item.get('title'):
                return None
            authors = [author.get('name', '') for author in (item.get('authors') or []) if author.get('name')]

            pub_date_str = item.get('publicationDate') or ''
            published_date = self._parse_date(pub_date_str) if pub_date_str else None

            pdf_url = ""
            if item.get('openAccessPdf'):
                open_access_pdf = item['openAccessPdf']
                if open_access_pdf.get('url'):
                    pdf_url = open_access_pdf['url']
                elif open_access_pdf.get('disclaimer'):
                    pdf_url = self._extract_url_from_disclaimer(open_access_pdf['disclaimer'])

            doi = ""
            if item.get('externalIds') and item['externalIds'].get('DOI'):
                doi = item['externalIds']['DOI']

            if not doi and item.get('abstract'):
                doi = extract_doi(item['abstract'])

            categories = item.get('fieldsOfStudy', [])
            if not categories:
                categories = []

            return Paper(
                paper_id=item['paperId'],
                title=item['title'],
                authors=authors,
                abstract=item.get('abstract') or '',
                url=item.get('url') or '',
                pdf_url=pdf_url,
                published_date=published_date,
                source="semantic",
                categories=categories,
                doi=doi,
                citations=item.get('citationCount') or 0,
            )

        except Exception as e:
            logger.warning(f"Failed to parse Semantic paper: {e}")
            return None

    @staticmethod
    def get_api_key() -> Optional[str]:
        """
        Get the Semantic Scholar API key from environment variables.
        Returns None if no API key is set or if it's empty, enabling unauthenticated access.
        """
        api_key = get_env("SEMANTIC_SCHOLAR_API_KEY", "")
        if not api_key or api_key.strip() == "":
            logger.warning("No SEMANTIC_SCHOLAR_API_KEY set or it's empty. Using unauthenticated access with lower rate limits.")
            return None
        return api_key.strip()

    def request_api(self, path: str, params: dict) -> dict:
        """
        Make a request to the Semantic Scholar API with optional API key.
        """
        max_retries = 3
        api_key = self.get_api_key()
        retry_delay = 5 if api_key is None else 2
        has_retried_without_key = False

        for attempt in range(max_retries):
            try:
                headers = {"x-api-key": api_key} if api_key else {}
                url = f"{self.SEMANTIC_BASE_URL}/{path}"
                response = self.session.get(url, params=params, headers=headers, timeout=30)

                if response.status_code == 403 and api_key and not has_retried_without_key:
                    logger.warning("Semantic Scholar API key was rejected (403). Retrying without API key.")
                    api_key = None
                    has_retried_without_key = True
                    continue

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after and retry_after.isdigit() else retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited (429). Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limited (429) after {max_retries} attempts. Please wait before making more requests.")
                        return {"error": "rate_limited", "status_code": 429, "message": "Too many requests. Please wait before retrying."}

                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403 and api_key and not has_retried_without_key:
                    logger.warning("Semantic Scholar API key was rejected (403). Retrying without API key.")
                    api_key = None
                    has_retried_without_key = True
                    continue
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = e.response.headers.get("Retry-After")
                        wait_time = int(retry_after) if retry_after and retry_after.isdigit() else retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited (429). Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limited (429) after {max_retries} attempts. Please wait before making more requests.")
                        return {"error": "rate_limited", "status_code": 429, "message": "Too many requests. Please wait before retrying."}
                else:
                    logger.error(f"HTTP Error requesting API: {e}")
                    return {"error": "http_error", "status_code": e.response.status_code, "message": str(e)}
            except Exception as e:
                logger.error(f"Error requesting API: {e}")
                return {"error": "general_error", "message": str(e)}

        return {"error": "max_retries_exceeded", "message": "Maximum retry attempts exceeded"}

    def search(
        self,
        query: str,
        year: Optional[str] = None,
        max_results: int = 10,
        fetch_details: bool = False,
        **kwargs,
    ) -> List[Paper]:
        """
        Search Semantic Scholar

        Args:
            query: Search query string
            year (Optional[str]): Filter by publication year. Supports several formats:
            - Single year: "2019"
            - Year range: "2016-2020"
            - Since year: "2010-"
            - Until year: "-2015"
            max_results: Maximum number of results to return
            fetch_details: Backward-compatible flag retained for older callers.
                Semantic search responses already include the fields this connector uses,
                so the current implementation does not perform extra per-paper detail fetches.

        Returns:
            List[Paper]: List of paper objects
        """
        papers = []

        try:
            fields = [
                "title",
                "abstract",
                "year",
                "citationCount",
                "authors",
                "url",
                "publicationDate",
                "externalIds",
                "fieldsOfStudy",
                "openAccessPdf",
            ]
            params = {
                "query": query,
                "limit": max_results,
                "fields": ",".join(fields),
            }
            if year:
                params["year"] = year
            response = self.request_api("paper/search", params)

            if isinstance(response, dict) and "error" in response:
                error_msg = response.get("message", "Unknown error")
                if response.get("error") == "rate_limited":
                    logger.error(f"Rate limited by Semantic Scholar API: {error_msg}")
                else:
                    logger.error(f"Semantic Scholar API error: {error_msg}")
                return papers

            if not hasattr(response, 'status_code') or response.status_code != 200:
                status_code = getattr(response, 'status_code', 'unknown')
                logger.error(f"Semantic Scholar search failed with status {status_code}")
                return papers

            data = response.json()
            results = data['data']

            if not results:
                logger.info("No results found for the query")
                return papers

            for i, item in enumerate(results):
                if len(papers) >= max_results:
                    break

                logger.info(f"Processing paper {i+1}/{min(len(results), max_results)}")
                paper = self._parse_paper(item)
                if paper:
                    papers.append(paper)

        except Exception as e:
            logger.error(f"Semantic Scholar search error: {e}")

        return papers[:max_results]

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        """
        Download PDF from Semantic Scholar

        Args:
            paper_id (str): Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
            save_path: Path to save the PDF

        Returns:
            str: Path to downloaded file or error message
        """
        try:
            paper = self.get_paper_details(paper_id)
            if not paper or not paper.pdf_url:
                return f"Error: Could not find PDF URL for paper {paper_id}"
            pdf_url = paper.pdf_url
            pdf_response = requests.get(pdf_url, timeout=30)
            pdf_response.raise_for_status()

            os.makedirs(save_path, exist_ok=True)

            safe_id = str(paper_id).replace('/', '_')
            filename = f"semantic_{safe_id}.pdf"
            pdf_path = os.path.join(save_path, filename)

            with open(pdf_path, "wb") as f:
                f.write(pdf_response.content)
            return pdf_path
        except Exception as e:
            logger.error(f"PDF download error: {e}")
            return f"Error downloading PDF: {e}"

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str:
        """
        Download and extract text from Semantic Scholar paper PDF

        Args:
            paper_id (str): Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
            save_path: Directory to save downloaded PDF

        Returns:
            str: Extracted text from the PDF or error message
        """
        try:
            os.makedirs(save_path, exist_ok=True)
            safe_id = str(paper_id).replace('/', '_')
            filename = f"semantic_{safe_id}.pdf"
            pdf_path = os.path.join(save_path, filename)

            if not os.path.exists(pdf_path):
                paper = self.get_paper_details(paper_id)
                if not paper or not paper.pdf_url:
                    return f"Error: Could not find PDF URL for paper {paper_id}"

                pdf_response = requests.get(paper.pdf_url, timeout=30)
                pdf_response.raise_for_status()

                with open(pdf_path, "wb") as f:
                    f.write(pdf_response.content)
            else:
                paper = self.get_paper_details(paper_id)

            reader = PdfReader(pdf_path)
            text = ""

            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page_text + "\n"
                except Exception as e:
                    logger.warning(
                        f"Failed to extract text from page {page_num + 1}: {e}"
                    )
                    continue

            if not text.strip():
                return (
                    f"PDF downloaded to {pdf_path}, but unable to extract readable text"
                )

            metadata = f"Title: {paper.title if paper else paper_id}\n"
            metadata += f"Authors: {', '.join(paper.authors) if paper else ''}\n"
            metadata += f"Published Date: {paper.published_date if paper else ''}\n"
            metadata += f"URL: {paper.url if paper else ''}\n"
            metadata += f"PDF downloaded to: {pdf_path}\n"
            metadata += "=" * 80 + "\n\n"

            return metadata + text.strip()

        except requests.RequestException as e:
            logger.error(f"Error downloading PDF: {e}")
            return f"Error downloading PDF: {e}"
        except Exception as e:
            logger.error(f"Read paper error: {e}")
            return f"Error reading paper: {e}"

    def get_paper_details(self, paper_id: str) -> Optional[Paper]:
        """
        Fetch detailed information for a specific Semantic Scholar paper

        Args:
            paper_id (str): Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")

        Returns:
            Paper: Detailed paper object with full metadata
        """
        try:
            fields = [
                "title",
                "abstract",
                "year",
                "citationCount",
                "authors",
                "url",
                "publicationDate",
                "externalIds",
                "fieldsOfStudy",
                "openAccessPdf",
            ]
            params = {
                "fields": ",".join(fields),
            }

            response = self.request_api(f"paper/{paper_id}", params)

            if isinstance(response, dict) and "error" in response:
                error_msg = response.get("message", "Unknown error")
                if response.get("error") == "rate_limited":
                    logger.error(f"Rate limited by Semantic Scholar API: {error_msg}")
                else:
                    logger.error(f"Semantic Scholar API error: {error_msg}")
                return None

            if not hasattr(response, 'status_code') or response.status_code != 200:
                status_code = getattr(response, 'status_code', 'unknown')
                logger.error(f"Semantic Scholar paper details fetch failed with status {status_code}")
                return None

            results = response.json()
            paper = self._parse_paper(results)
            if paper:
                return paper
            else:
                return None
        except Exception as e:
            logger.error(f"Error fetching paper details for {paper_id}: {e}")
            return None


    def get_references(self, paper_id: str, max_results: int = 20) -> List[Paper]:
        """Get papers referenced by the given paper (backward snowball).

        Args:
            paper_id: Semantic Scholar paper ID or DOI:xxx / ARXIV:xxx format.
            max_results: Maximum number of references to return.
        Returns:
            List of Paper objects for the referenced papers.
        """
        try:
            fields = [
                "title", "abstract", "year", "citationCount", "authors",
                "url", "publicationDate", "externalIds", "fieldsOfStudy", "openAccessPdf",
            ]
            params = {"fields": ",".join(fields), "limit": max_results}
            response = self.request_api(f"paper/{paper_id}/references", params)

            if isinstance(response, dict) and "error" in response:
                logger.error(f"get_references error: {response.get('message')}")
                return []
            if not hasattr(response, "status_code") or response.status_code != 200:
                return []

            data = response.json()
            papers: List[Paper] = []
            for item in (data.get("data") or []):
                cited = item.get("citedPaper")
                if not cited or not cited.get("paperId"):
                    continue
                paper = self._parse_paper(cited)
                if paper:
                    papers.append(paper)
            return papers[:max_results]
        except Exception as e:
            logger.error(f"get_references failed for {paper_id}: {e}")
            return []

    def get_citations(self, paper_id: str, max_results: int = 20) -> List[Paper]:
        """Get papers that cite the given paper (forward snowball).

        Args:
            paper_id: Semantic Scholar paper ID or DOI:xxx / ARXIV:xxx format.
            max_results: Maximum number of citing papers to return.
        Returns:
            List of Paper objects for the citing papers.
        """
        try:
            fields = [
                "title", "abstract", "year", "citationCount", "authors",
                "url", "publicationDate", "externalIds", "fieldsOfStudy", "openAccessPdf",
            ]
            params = {"fields": ",".join(fields), "limit": max_results}
            response = self.request_api(f"paper/{paper_id}/citations", params)

            if isinstance(response, dict) and "error" in response:
                logger.error(f"get_citations error: {response.get('message')}")
                return []
            if not hasattr(response, "status_code") or response.status_code != 200:
                return []

            data = response.json()
            papers: List[Paper] = []
            for item in (data.get("data") or []):
                citing = item.get("citingPaper")
                if not citing or not citing.get("paperId"):
                    continue
                paper = self._parse_paper(citing)
                if paper:
                    papers.append(paper)
            return papers[:max_results]
        except Exception as e:
            logger.error(f"get_citations failed for {paper_id}: {e}")
            return []
