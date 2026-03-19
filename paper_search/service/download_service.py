"""Download service with OA fallback chain."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import List, Optional

import httpx

from ..connectors.registry import ConnectorRegistry
from ..connectors.unpaywall import UnpaywallResolver
from ..connectors.sci_hub import SciHubFetcher

logger = logging.getLogger(__name__)


class DownloadService:
    """Orchestrates PDF downloads with a multi-stage fallback chain.

    Fallback order:
      1. Source-native ``download_pdf`` via the connector registry.
      2. OA repository search (openaire -> core -> europepmc -> pmc).
      3. Unpaywall DOI resolution.
      4. Sci-Hub (optional, last resort).
    """

    REPOSITORY_FALLBACK_SOURCES = ("openaire", "core", "europepmc", "pmc")

    def __init__(self, registry: ConnectorRegistry):
        self.registry = registry
        self._unpaywall = UnpaywallResolver()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def download(
        self,
        source: str,
        paper_id: str,
        doi: str = "",
        title: str = "",
        save_path: str = "./downloads",
        use_scihub: bool = True,
        scihub_base_url: str = "https://sci-hub.se",
    ) -> str:
        """Try source-native download, OA repositories, Unpaywall, then optional Sci-Hub.

        Args:
            source: Source name (e.g. ``arxiv``, ``semantic``, ``crossref``).
            paper_id: Source-native paper identifier.
            doi: Optional DOI used for repository/Unpaywall/Sci-Hub fallback.
            title: Optional title used for repository/Sci-Hub fallback when DOI is unavailable.
            save_path: Directory to save downloaded files.
            use_scihub: Whether to fallback to Sci-Hub after OA attempts fail.
            scihub_base_url: Sci-Hub mirror URL for fallback.

        Returns:
            Download path on success or explanatory error message.
        """
        source_name = source.strip().lower()
        attempt_errors: List[str] = []

        # --- Stage 1: primary source connector ---
        primary_error = ""
        connector = self.registry.get(source_name)
        if connector is not None:
            try:
                primary_result = await asyncio.to_thread(
                    connector.download_pdf, paper_id, save_path
                )
                if isinstance(primary_result, str) and os.path.exists(primary_result):
                    return primary_result
                if isinstance(primary_result, str) and primary_result:
                    primary_error = primary_result
            except Exception as exc:
                primary_error = str(exc)
                logger.warning(
                    "Primary download failed for %s/%s: %s",
                    source_name,
                    paper_id,
                    exc,
                )
        else:
            primary_error = f"Unsupported source '{source_name}' for primary download."

        if primary_error:
            attempt_errors.append(f"primary: {primary_error}")

        # --- Stage 2: OA repository fallback ---
        repository_result, repository_error = await self._try_repository_fallback(
            doi, title, save_path
        )
        if repository_result:
            return repository_result
        if repository_error:
            attempt_errors.append(f"repositories: {repository_error}")

        # --- Stage 3: Unpaywall ---
        normalized_doi = (doi or "").strip()
        if normalized_doi:
            unpaywall_url = await asyncio.to_thread(
                self._unpaywall.resolve_best_pdf_url, normalized_doi
            )
            if unpaywall_url:
                unpaywall_result = await self._download_from_url(
                    unpaywall_url, save_path, f"unpaywall_{normalized_doi}"
                )
                if unpaywall_result:
                    return unpaywall_result
                attempt_errors.append("unpaywall: resolved OA URL but download failed")
            else:
                attempt_errors.append(
                    "unpaywall: no OA URL found "
                    "(or PAPER_SEARCH_MCP_UNPAYWALL_EMAIL/UNPAYWALL_EMAIL missing)"
                )
        else:
            attempt_errors.append("unpaywall: DOI not provided")

        # --- Stage 4: Sci-Hub (optional) ---
        if not use_scihub:
            return (
                "Download failed after OA fallback chain. Details: "
                + " | ".join(attempt_errors)
            )

        fallback_identifier = (
            (doi or "").strip() or (title or "").strip() or paper_id
        )
        fetcher = SciHubFetcher(base_url=scihub_base_url, output_dir=save_path)
        fallback_result = await asyncio.to_thread(
            fetcher.download_pdf, fallback_identifier
        )
        if fallback_result:
            return fallback_result

        return (
            "Download failed after OA fallback chain and Sci-Hub fallback. Details: "
            + " | ".join(attempt_errors)
        )

    async def download_from_source(
        self, source: str, paper_id: str, save_path: str = "./downloads"
    ) -> str:
        """Direct download from a specific source connector (no fallback).

        Args:
            source: Source name.
            paper_id: Source-native paper identifier.
            save_path: Directory to save the PDF.

        Returns:
            Downloaded file path on success or error message.
        """
        source_name = source.strip().lower()
        connector = self.registry.get(source_name)
        if connector is None:
            return f"Unsupported source '{source_name}'."

        try:
            result = await asyncio.to_thread(
                connector.download_pdf, paper_id, save_path
            )
            return result
        except Exception as exc:
            return f"Download from {source_name} failed: {exc}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _try_repository_fallback(
        self, doi: str, title: str, save_path: str
    ) -> tuple[Optional[str], str]:
        """Try OA repositories: openaire -> core -> europepmc -> pmc.

        Returns:
            ``(path, "")`` on success, ``(None, error_summary)`` on failure.
        """
        query_candidates = [(doi or "").strip(), (title or "").strip()]
        query_candidates = [c for c in query_candidates if c]
        if not query_candidates:
            return None, "no DOI/title provided for repository fallback"

        repository_errors: List[str] = []

        for repo_name in self.REPOSITORY_FALLBACK_SOURCES:
            searcher = self.registry.get(repo_name)
            if searcher is None:
                continue

            for query in query_candidates:
                try:
                    papers = await asyncio.to_thread(
                        searcher.search, query, max_results=3
                    )
                except Exception as exc:
                    repository_errors.append(f"{repo_name}:{exc}")
                    continue

                if not papers:
                    continue

                for paper in papers:
                    pdf_url = (getattr(paper, "pdf_url", "") or "").strip()
                    if not pdf_url:
                        continue

                    paper_id = str(
                        getattr(paper, "paper_id", "") or query
                    ).strip()
                    downloaded = await self._download_from_url(
                        pdf_url, save_path, f"{repo_name}_{paper_id}"
                    )
                    if downloaded:
                        return downloaded, ""

        return None, "; ".join(repository_errors)

    @staticmethod
    async def _download_from_url(
        pdf_url: str, save_path: str, filename_hint: str = "paper"
    ) -> Optional[str]:
        """Download PDF from a direct URL using httpx.

        Returns:
            Path to the saved file on success, ``None`` on failure.
        """
        if not pdf_url:
            return None

        os.makedirs(save_path, exist_ok=True)
        output_name = f"{DownloadService._safe_filename(filename_hint)}.pdf"
        output_path = os.path.join(save_path, output_name)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=30
            ) as client:
                response = await client.get(pdf_url)

            if response.status_code >= 400 or not response.content:
                return None

            content_type = (response.headers.get("content-type") or "").lower()
            is_pdf = (
                "pdf" in content_type
                or response.content.startswith(b"%PDF")
                or pdf_url.lower().endswith(".pdf")
            )
            if not is_pdf:
                logger.warning(
                    "Resolved URL is not a PDF candidate: %s (content-type=%s)",
                    pdf_url,
                    content_type,
                )
                return None

            with open(output_path, "wb") as file_obj:
                file_obj.write(response.content)

            return output_path
        except Exception as exc:
            logger.warning("Direct URL download failed for %s: %s", pdf_url, exc)
            return None

    @staticmethod
    def _safe_filename(filename_hint: str, default: str = "paper") -> str:
        """Sanitise a hint string into a filesystem-safe filename (without extension)."""
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename_hint).strip("._")
        if not safe:
            return default
        return safe[:120]
