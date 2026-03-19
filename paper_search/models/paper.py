from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Paper(BaseModel):
    """Standardized academic paper model."""

    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    doi: str = ""
    published_date: Optional[datetime] = None
    pdf_url: str = ""
    url: str = ""
    source: str = ""

    updated_date: Optional[datetime] = None
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    citations: int = 0
    references: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize for API / MCP responses (flat string fields)."""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": "; ".join(self.authors) if self.authors else "",
            "abstract": self.abstract,
            "doi": self.doi,
            "published_date": self.published_date.isoformat() if self.published_date else "",
            "pdf_url": self.pdf_url,
            "url": self.url,
            "source": self.source,
            "updated_date": self.updated_date.isoformat() if self.updated_date else "",
            "categories": "; ".join(self.categories) if self.categories else "",
            "keywords": "; ".join(self.keywords) if self.keywords else "",
            "citations": self.citations,
            "references": "; ".join(self.references) if self.references else "",
            "extra": str(self.extra) if self.extra else "",
        }


class SearchResult(BaseModel):
    """Result of a multi-source search."""

    query: str
    sources_requested: str
    sources_used: list[str] = Field(default_factory=list)
    source_results: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    papers: list[Paper] = Field(default_factory=list)
    total: int = 0
    raw_total: int = 0


class SnowballResult(BaseModel):
    """Result of a snowball (citation network) search."""

    seed_paper_id: str
    direction: str
    depth: int
    total: int = 0
    raw_total: int = 0
    papers: list[Paper] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
