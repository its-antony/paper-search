"""Connector registry — auto-discovers and manages platform connectors."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from ..config import get_env
from .base import PaperConnector

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Global mapping: name -> connector class
_REGISTRY: Dict[str, Type[PaperConnector]] = {}


def register(name: str):
    """Class decorator to register a connector under *name*.

    Usage::

        @register("arxiv")
        class ArxivConnector(PaperConnector):
            ...
    """

    def decorator(cls: Type[PaperConnector]):
        _REGISTRY[name] = cls
        return cls

    return decorator


class ConnectorRegistry:
    """Instantiates and holds live connector instances based on config."""

    def __init__(self, *, extra_connectors: Optional[Dict[str, Type[PaperConnector]]] = None):
        self._instances: Dict[str, PaperConnector] = {}

        # Auto-import all modules in the connectors package so that
        # @register decorators execute.
        self._auto_import()

        if extra_connectors:
            _REGISTRY.update(extra_connectors)

        self._instantiate_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[PaperConnector]:
        return self._instances.get(name)

    def all_names(self) -> List[str]:
        return list(self._instances.keys())

    def all_connectors(self) -> Dict[str, PaperConnector]:
        return dict(self._instances)

    def __contains__(self, name: str) -> bool:
        return name in self._instances

    def __len__(self) -> int:
        return len(self._instances)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_import() -> None:
        """Import every .py module in the connectors package."""
        import paper_search.connectors as pkg

        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            if modname.startswith("_") or modname in ("base", "registry"):
                continue
            try:
                importlib.import_module(f"paper_search.connectors.{modname}")
            except Exception as exc:
                logger.warning("Failed to import connector module %s: %s", modname, exc)

    def _instantiate_all(self) -> None:
        for name, cls in _REGISTRY.items():
            caps = getattr(cls, "capabilities", None)
            if caps and caps.requires_key:
                key_value = get_env(caps.requires_key, "")
                if not key_value:
                    logger.debug(
                        "Skipping connector %s — required key %s not set.",
                        name,
                        caps.requires_key,
                    )
                    continue
            try:
                self._instances[name] = cls()
            except Exception as exc:
                logger.warning("Failed to instantiate connector %s: %s", name, exc)
