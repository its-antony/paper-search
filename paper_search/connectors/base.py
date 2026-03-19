"""Base class for all academic paper connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from ..models.paper import Paper


@dataclass
class ConnectorCapabilities:
    """Declares what a connector can do."""

    search: bool = True
    download: bool = False
    read: bool = False
    requires_key: str | None = None  # env var name if API key is required to activate


class PaperConnector(ABC):
    """Abstract base for all platform connectors.

    Subclasses MUST define ``capabilities`` and implement ``search``.
    ``download_pdf`` and ``read_paper`` have sensible defaults that raise
    ``NotImplementedError``; override only when supported.
    """

    capabilities: ConnectorCapabilities = ConnectorCapabilities()

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Paper]:
        """Search papers matching the query."""

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support PDF downloads."
        )

    def read_paper(self, paper_id: str, save_path: str = "./downloads") -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support reading paper content."
        )
