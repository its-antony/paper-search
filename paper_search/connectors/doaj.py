# paper_search/connectors/doaj.py
"""Searcher for DOAJ (Directory of Open Access Journals).

DOAJ is a community-curated online directory that indexes and provides
access to high quality, open access, peer-reviewed journals.

API Documentation: https://doaj.org/api/v2
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import requests
import logging
import time
from urllib.parse import quote
from ..models.paper import Paper
from ..utils import extract_doi
from ..config import get_env
from .base import PaperConnector, ConnectorCapabilities
from .registry import register

logger = logging.getLogger(__name__)


@register("doaj")
class DOAJConnector(PaperConnector):
    """Searcher for DOAJ (Directory of Open Access Journals)."""

    capabilities = ConnectorCapabilities(search=True, download=True, read=True)

    BASE_URL = "https://doaj.org/api"
    USER_AGENT = "paper-search-mcp/0.1.3 (https://github.com/openags/paper-search-mcp)"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize DOAJ searcher.

        Args:
            api_key: DOAJ API key (optional, free registration required)
                     Can also be set via DOAJ_API_KEY environment variable.
        """
        self.api_key = api_key or get_env("DOAJ_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/json'
        })

        if self.api_key:
            self.session.headers.update({'X-API-Key': self.api_key})
            logger.info("DOAJ API key configured")
        else:
            logger.warning(
                "No DOAJ API key provided. Searches will use public access "
                "with rate limits (100 requests/hour). "
                "Get a free API key at: https://doaj.org/apply-for-api-key/"
            )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Paper]:
        """Search DOAJ for open access journal articles.

        Args:
            query: Search query string (supports Lucene query syntax)
            max_results: Maximum number of results (1-100, DOAJ default: 10)
            **kwargs: Additional parameters:
                - year: Filter by publication year (e.g., 2023)
                - journal: Filter by journal ISSN or title
                - publisher: Filter by publisher
                - country: Filter by country
                - language: Filter by language (e.g., 'en')
                - subject: Filter by subject category
                - open_access: Filter by open access status (default: True for DOAJ)
                - sort: Sort field (e.g., 'created_date', 'title')
                - sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            List of Paper objects
        """
        if max_results > 100:
            max_results = 100
        if max_results < 1:
            max_results = 10

        papers = []
        page_size = min(max_results, 100)
        page = 1

        try:
            lucene_query = self._build_lucene_query(query, kwargs)

            params = {
                'page': page,
                'pageSize': page_size,
                'query': lucene_query
            }

            if 'sort' in kwargs:
                params['sort'] = kwargs['sort']
                if 'sort_dir' in kwargs and kwargs['sort_dir'] in ('asc', 'desc'):
                    params['sort_dir'] = kwargs['sort_dir']

            encoded_query = quote(query.strip() or "*", safe="")
            search_url = f"{self.BASE_URL}/search/articles/{encoded_query}"
            response = self.session.get(
                search_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                logger.error(f"DOAJ API error: {data['error']}")
                return papers

            total = data.get('total', 0)
            logger.info(f"DOAJ search found {total} total results")

            results = data.get('results', [])
            for item in results:
                if len(papers) >= max_results:
                    break

                try:
                    paper = self._parse_doaj_item(item)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.warning(f"Error parsing DOAJ item: {e}")
                    continue

            time.sleep(0.5 if self.api_key else 1.0)

        except requests.exceptions.RequestException as e:
            logger.error(f"DOAJ API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                if e.response.status_code == 429:
                    logger.warning("DOAJ rate limit exceeded. Consider using API key.")
        except ValueError as e:
            logger.error(f"Failed to parse DOAJ JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in DOAJ search: {e}")

        return papers[:max_results]

    def _build_lucene_query(self, query: str, filters: Dict[str, Any]) -> str:
        """Build Lucene query string for DOAJ API."""
        query_parts = []

        if query:
            query_parts.append(f"({query})")

        if 'year' in filters and filters['year']:
            year = filters['year']
            if isinstance(year, str) and '-' in year:
                year_range = year.split('-')
                if len(year_range) == 2:
                    query_parts.append(f"year:[{year_range[0]} TO {year_range[1]}]")
            else:
                query_parts.append(f"year:{year}")

        if 'journal' in filters and filters['journal']:
            journal = filters['journal']
            if len(journal) == 9 and '-' in journal:
                query_parts.append(f"issn:{journal}")
            else:
                query_parts.append(f"journal.title:{journal}")

        if 'publisher' in filters and filters['publisher']:
            query_parts.append(f"publisher:{filters['publisher']}")

        if 'country' in filters and filters['country']:
            query_parts.append(f"country:{filters['country']}")

        if 'language' in filters and filters['language']:
            query_parts.append(f"language:{filters['language']}")

        if 'subject' in filters and filters['subject']:
            query_parts.append(f"subject:{filters['subject']}")

        if 'open_access' in filters and filters['open_access'] is not None:
            pass

        if len(query_parts) == 0:
            return "*:*"

        return " AND ".join(f"({part})" for part in query_parts)

    def _parse_doaj_item(self, item: Dict[str, Any]) -> Optional[Paper]:
        """Parse DOAJ API response item to Paper object."""
        try:
            bibjson = item.get('bibjson', {})
            if not bibjson:
                return None

            title = bibjson.get('title', '')
            if not title:
                return None

            authors = []
            author_list = bibjson.get('author', [])
            for author in author_list:
                name = author.get('name', '')
                if name:
                    authors.append(name.strip())

            abstract = ''
            abstract_elem = bibjson.get('abstract')
            if isinstance(abstract_elem, str):
                abstract = abstract_elem
            elif isinstance(abstract_elem, dict):
                abstract = abstract_elem.get('text', '')

            doi = ''
            identifiers = bibjson.get('identifier', [])
            for ident in identifiers:
                if ident.get('type') == 'doi' and ident.get('id'):
                    doi = ident['id']
                    break

            published_date = None
            year = bibjson.get('year')
            month = bibjson.get('month', 1)
            day = bibjson.get('day', 1)

            if year:
                try:
                    published_date = datetime(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    try:
                        published_date = datetime(int(year), 1, 1)
                    except (ValueError, TypeError):
                        pass

            journal = bibjson.get('journal', {})
            journal_title = journal.get('title', '')
            journal_issn = journal.get('issn', '')
            if isinstance(journal_issn, list):
                journal_issn = journal_issn[0] if journal_issn else ''

            keywords = []
            keywords_list = bibjson.get('keywords', [])
            if isinstance(keywords_list, list):
                keywords = [kw.strip() for kw in keywords_list if isinstance(kw, str) and kw.strip()]

            categories = []
            subject_list = bibjson.get('subject', [])
            if isinstance(subject_list, list):
                categories = [sub.get('term', '') for sub in subject_list if isinstance(sub, dict)]
                categories = [cat for cat in categories if cat]

            pdf_url = ''
            url = item.get('admin', {}).get('url', '')

            links = bibjson.get('link', [])
            for link in links:
                if isinstance(link, dict):
                    link_type = link.get('type', '')
                    link_url = link.get('url', '')
                    if link_type == 'fulltext' and link_url:
                        if link_url.lower().endswith('.pdf'):
                            pdf_url = link_url
                        elif not url:
                            url = link_url

            if not pdf_url and 'fulltext' in bibjson:
                fulltext = bibjson.get('fulltext')
                if isinstance(fulltext, str) and fulltext.lower().endswith('.pdf'):
                    pdf_url = fulltext

            if not url and doi:
                url = f"https://doi.org/{doi}"
            elif not url:
                article_id = item.get('id', '')
                if article_id:
                    url = f"https://doaj.org/article/{article_id}"

            paper = Paper(
                paper_id=item.get('id', '') or doi or f"doaj_{hash(title) & 0xffffffff:08x}",
                title=title,
                authors=authors,
                abstract=abstract,
                doi=doi,
                published_date=published_date,
                pdf_url=pdf_url,
                url=url,
                source='doaj',
                categories=categories,
                keywords=keywords
            )

            paper.extra = {
                'journal': journal_title,
                'issn': journal_issn,
                'publisher': journal.get('publisher', {}),
                'country': journal.get('country', ''),
                'language': bibjson.get('language', ''),
                'license': bibjson.get('license', [{}])[0] if isinstance(bibjson.get('license'), list) else {},
                'start_page': bibjson.get('start_page', ''),
                'end_page': bibjson.get('end_page', ''),
                'volume': bibjson.get('volume', ''),
                'number': bibjson.get('number', '')
            }

            return paper

        except Exception as e:
            logger.warning(f"Error parsing DOAJ article: {e}")
            return None

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        """Download PDF for a DOAJ article."""
        papers = self.search(paper_id, max_results=1)
        if not papers:
            raise ValueError(f"DOAJ article not found: {paper_id}")

        paper = papers[0]
        if not paper.pdf_url:
            if paper.doi:
                pdf_url = f"https://doi.org/{paper.doi}"
                paper.pdf_url = pdf_url
            else:
                raise ValueError(f"No PDF available for DOAJ article: {paper_id}")

        import os
        response = self.session.get(paper.pdf_url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not paper.pdf_url.lower().endswith('.pdf'):
            logger.warning(f"Response may not be PDF: {content_type}")

        os.makedirs(save_path, exist_ok=True)

        safe_id = paper_id.replace('/', '_').replace(':', '_')
        filename = f"doaj_{safe_id}.pdf"
        output_file = os.path.join(save_path, filename)

        with open(output_file, 'wb') as f:
            f.write(response.content)

        logger.info(f"Downloaded PDF to {output_file}")
        return output_file

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str:
        """Read paper text from PDF."""
        try:
            pdf_path = self.download_pdf(paper_id, save_path)

            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error reading DOAJ paper {paper_id}: {e}")
            raise NotImplementedError(
                f"Cannot read paper from DOAJ: {e}"
            )
