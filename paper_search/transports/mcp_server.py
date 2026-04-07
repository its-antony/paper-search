"""MCP transport layer — thin adapter over service layer."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..service.search_service import PaperSearchService
from ..service.download_service import DownloadService
from ..service.export_service import ExportService
from ..connectors.sci_hub import SciHubFetcher

mcp = FastMCP("paper_search_server")
search_service = PaperSearchService()
download_service = DownloadService(registry=search_service.registry)
export_service = ExportService()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ========== Static top-level tools ==========

@mcp.tool()
async def search_papers(
    query: str,
    max_results_per_source: int = 5,
    sources: str = "all",
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """Unified search across all configured academic platforms.

    Args:
        query: Search query string.
        max_results_per_source: Max results per source.
        sources: Comma-separated source names or 'all'.
        year: Optional year filter for Semantic Scholar.
    """
    result = await search_service.search(query, sources, max_results_per_source, year)
    data = result.model_dump()
    data["papers"] = [p.to_api_dict() for p in result.papers]
    return data


@mcp.tool()
async def download_with_fallback(
    source: str,
    paper_id: str,
    doi: str = "",
    title: str = "",
    save_path: str = "./downloads",
    use_scihub: bool = True,
    scihub_base_url: str = "https://sci-hub.se",
) -> str:
    """Try source-native download, OA repositories, Unpaywall, then optional Sci-Hub."""
    return await download_service.download(
        source, paper_id, doi, title, save_path, use_scihub, scihub_base_url
    )


@mcp.tool()
async def snowball_search(
    paper_id: str,
    direction: str = "both",
    max_results_per_direction: int = 20,
    depth: int = 1,
) -> Dict[str, Any]:
    """Snowball search: find references and/or citations of a seed paper recursively.

    Args:
        paper_id: Semantic Scholar paper ID, or DOI:<doi>, ARXIV:<id>, etc.
        direction: 'backward' (references), 'forward' (citations), or 'both'.
        max_results_per_direction: Max papers per direction per layer.
        depth: Recursion depth (1-3).
    """
    result = await search_service.snowball(
        paper_id, direction, max_results_per_direction, depth
    )
    data = result.model_dump()
    data["papers"] = [p.to_api_dict() for p in result.papers]
    return data


@mcp.tool()
async def recommend_papers(
    paper_id: str,
    max_results: int = 10,
) -> Dict[str, Any]:
    """Find similar papers using embedding-based recommendations (not citation graph).

    Uses Semantic Scholar's paper embeddings to find content-similar papers.

    Args:
        paper_id: Semantic Scholar paper ID, or DOI:<doi>, ARXIV:<id>, etc.
        max_results: Max number of recommendations.
    """
    result = await search_service.recommend(paper_id, max_results)
    data = result.model_dump()
    data["papers"] = [p.to_api_dict() for p in result.papers]
    return data


@mcp.tool()
async def export_papers(
    papers: List[Dict[str, Any]],
    format: str = "csv",
    save_path: str = "./exports",
    filename: str = "papers",
) -> str:
    """Export paper dicts to CSV, RIS, or BibTeX."""
    return export_service.export_from_dicts(papers, format, save_path, filename)


@mcp.tool()
async def get_crossref_paper_by_doi(doi: str) -> Dict:
    """Get a specific paper from CrossRef by its DOI."""
    connector = search_service.registry.get("crossref")
    if connector is None:
        return {}
    paper = await asyncio.to_thread(connector.get_paper_by_doi, doi)
    return paper.to_api_dict() if paper else {}


@mcp.tool()
async def download_scihub(
    identifier: str,
    save_path: str = "./downloads",
    base_url: str = "https://sci-hub.se",
) -> str:
    """Download paper PDF via Sci-Hub (optional fallback)."""
    fetcher = SciHubFetcher(base_url=base_url, output_dir=save_path)
    result = await asyncio.to_thread(fetcher.download_pdf, identifier)
    return result or "Sci-Hub download failed."


# ========== Static special-parameter tools ==========

@mcp.tool()
async def search_semantic(
    query: str, year: Optional[str] = None, max_results: int = 10
) -> List[Dict]:
    """Search academic papers from Semantic Scholar.

    Args:
        query: Search query string.
        year: Year filter (e.g., '2019', '2016-2020', '2010-', '-2015').
        max_results: Maximum number of papers to return.
    """
    connector = search_service.registry.get("semantic")
    if connector is None:
        return []
    kwargs = {"year": year} if year else {}
    papers = await search_service._async_search(connector, query, max_results, **kwargs)
    return [p.to_api_dict() for p in papers]


@mcp.tool()
async def search_crossref(
    query: str,
    max_results: int = 10,
    filter: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
) -> List[Dict]:
    """Search academic papers from CrossRef database.

    Args:
        query: Search query string.
        max_results: Maximum number of papers to return.
        filter: CrossRef filter (e.g., 'has-full-text:true,from-pub-date:2020').
        sort: Sort field ('relevance', 'published', etc.).
        order: Sort order ('asc' or 'desc').
    """
    connector = search_service.registry.get("crossref")
    if connector is None:
        return []
    kwargs = {k: v for k, v in {"filter": filter, "sort": sort, "order": order}.items() if v is not None}
    papers = await search_service._async_search(connector, query, max_results, **kwargs)
    return [p.to_api_dict() for p in papers]


@mcp.tool()
async def search_iacr(
    query: str, max_results: int = 10, fetch_details: bool = True
) -> List[Dict]:
    """Search academic papers from IACR ePrint Archive.

    Args:
        query: Search query string.
        max_results: Maximum number of papers to return.
        fetch_details: Whether to fetch detailed information for each paper.
    """
    connector = search_service.registry.get("iacr")
    if connector is None:
        return []
    papers = await asyncio.to_thread(connector.search, query, max_results, fetch_details)
    return [p.to_api_dict() for p in (papers or [])]


# ========== Dynamic tool registration ==========

_STATIC_SEARCH_TOOLS = {"semantic", "crossref", "iacr"}


def _register_search_tool(name: str) -> None:
    _name = name

    async def tool_fn(query: str, max_results: int = 10) -> List[Dict]:
        connector = search_service.registry.get(_name)
        if connector is None:
            return []
        papers = await search_service._async_search(connector, query, max_results)
        return [p.to_api_dict() for p in papers]

    tool_fn.__name__ = f"search_{name}"
    tool_fn.__doc__ = f"Search academic papers from {name}."
    tool_fn.__qualname__ = f"search_{name}"
    mcp.tool()(tool_fn)


def _register_download_tool(name: str) -> None:
    _name = name

    async def tool_fn(paper_id: str, save_path: str = "./downloads") -> str:
        connector = search_service.registry.get(_name)
        if connector is None:
            return f"Connector {_name} not available."
        return await asyncio.to_thread(connector.download_pdf, paper_id, save_path)

    tool_fn.__name__ = f"download_{name}"
    tool_fn.__doc__ = f"Download PDF of a {name} paper."
    tool_fn.__qualname__ = f"download_{name}"
    mcp.tool()(tool_fn)


def _register_read_tool(name: str) -> None:
    _name = name

    async def tool_fn(paper_id: str, save_path: str = "./downloads") -> str:
        connector = search_service.registry.get(_name)
        if connector is None:
            return f"Connector {_name} not available."
        return await asyncio.to_thread(connector.read_paper, paper_id, save_path)

    tool_fn.__name__ = f"read_{name}_paper"
    tool_fn.__doc__ = f"Read and extract text content from a {name} paper."
    tool_fn.__qualname__ = f"read_{name}_paper"
    mcp.tool()(tool_fn)


def _register_platform_tools() -> None:
    for name in search_service.available_sources():
        connector = search_service.registry.get(name)
        if connector is None:
            continue
        caps = connector.capabilities

        if name not in _STATIC_SEARCH_TOOLS:
            _register_search_tool(name)

        if caps.download:
            _register_download_tool(name)

        if caps.read:
            _register_read_tool(name)


_register_platform_tools()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Paper Search MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind for SSE/HTTP (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE/HTTP (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport in ("sse", "streamable-http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        # Allow LAN access by disabling DNS rebinding protection
        mcp.settings.transport_security.enable_dns_rebinding_protection = False
        # Stateless mode: no session affinity required, works behind LB/CDN
        mcp.settings.stateless_http = True

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
