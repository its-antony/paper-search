# paper_search/connectors/arxiv.py
from typing import List
from datetime import datetime
import requests
import feedparser
import time
from ..models.paper import Paper
from ..utils import extract_doi
from .base import PaperConnector, ConnectorCapabilities
from .registry import register
from PyPDF2 import PdfReader
import os


@register("arxiv")
class ArxivConnector(PaperConnector):
    """Searcher for arXiv papers"""
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)
    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'paper-search-mcp/1.0 (mailto:openags@example.com)',
            'Accept': 'application/atom+xml, application/xml;q=0.9, */*;q=0.8',
        })

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Paper]:
        params = {
            'search_query': f'all:{query}',
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        response = None
        for attempt in range(3):
            try:
                response = self.session.get(self.BASE_URL, params=params, timeout=30)
            except requests.RequestException:
                time.sleep((attempt + 1) * 1.5)
                continue
            if response.status_code == 200:
                break
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep((attempt + 1) * 1.5)
                continue
            break

        if response is None or response.status_code != 200:
            return []

        feed = feedparser.parse(response.content)
        papers = []
        for entry in feed.entries:
            try:
                authors = [author.name for author in entry.authors]
                published = datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%SZ')
                updated = datetime.strptime(entry.updated, '%Y-%m-%dT%H:%M:%SZ')
                pdf_url = next((link.href for link in entry.links if link.type == 'application/pdf'), '')

                # Try to extract DOI from entry.doi or links or summary
                doi = entry.get('doi', '') or extract_doi(entry.summary) or extract_doi(entry.id)
                for link in entry.links:
                    if link.get('title') == 'doi':
                        doi = doi or extract_doi(link.href)

                papers.append(Paper(
                    paper_id=entry.id.split('/')[-1],
                    title=entry.title,
                    authors=authors,
                    abstract=entry.summary,
                    url=entry.id,
                    pdf_url=pdf_url,
                    published_date=published,
                    updated_date=updated,
                    source='arxiv',
                    categories=[tag.term for tag in entry.tags],
                    keywords=[],
                    doi=doi
                ))
            except Exception as e:
                print(f"Error parsing arXiv entry: {e}")
        return papers

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        response = requests.get(pdf_url)
        os.makedirs(save_path, exist_ok=True)
        output_file = f"{save_path}/{paper_id}.pdf"
        with open(output_file, 'wb') as f:
            f.write(response.content)
        return output_file

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str:
        """Read a paper and convert it to text format.

        Args:
            paper_id: arXiv paper ID
            save_path: Directory where the PDF is/will be saved

        Returns:
            str: The extracted text content of the paper
        """
        # First ensure we have the PDF
        pdf_path = f"{save_path}/{paper_id}.pdf"
        if not os.path.exists(pdf_path):
            pdf_path = self.download_pdf(paper_id, save_path)

        # Read the PDF
        try:
            reader = PdfReader(pdf_path)
            text = ""

            # Extract text from each page
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text.strip()
        except Exception as e:
            print(f"Error reading PDF for paper {paper_id}: {e}")
            return ""
