"""Tests for DownloadService."""
import pytest

from paper_search.service.download_service import DownloadService
from paper_search.connectors.registry import ConnectorRegistry


def test_download_service_init():
    reg = ConnectorRegistry()
    ds = DownloadService(registry=reg)
    assert ds is not None
    assert ds.registry is reg


def test_safe_filename_basic():
    assert DownloadService._safe_filename("hello world") == "hello_world"
    assert DownloadService._safe_filename("") == "paper"
    assert DownloadService._safe_filename("a" * 200) == "a" * 120
    assert DownloadService._safe_filename("...") == "paper"


def test_safe_filename_special_chars():
    result = DownloadService._safe_filename("10.1234/some-doi")
    assert "/" not in result
    assert result  # non-empty


@pytest.mark.asyncio
async def test_download_unsupported_source():
    reg = ConnectorRegistry()
    ds = DownloadService(registry=reg)
    result = await ds.download(source="nonexistent", paper_id="123", use_scihub=False)
    assert "failed" in result.lower() or "unsupported" in result.lower()


@pytest.mark.asyncio
async def test_download_from_source_unsupported():
    reg = ConnectorRegistry()
    ds = DownloadService(registry=reg)
    result = await ds.download_from_source(source="nonexistent", paper_id="123")
    assert "unsupported" in result.lower()
