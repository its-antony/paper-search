from datetime import datetime
from paper_search.models.paper import Paper, SearchResult, SnowballResult


def test_paper_creation_minimal():
    p = Paper(paper_id="123", title="Test")
    assert p.paper_id == "123"
    assert p.authors == []
    assert p.doi == ""


def test_paper_creation_full():
    p = Paper(
        paper_id="2106.12345",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="An abstract",
        doi="10.1234/test",
        published_date=datetime(2021, 6, 1),
        pdf_url="https://example.com/paper.pdf",
        url="https://example.com/paper",
        source="arxiv",
    )
    assert p.source == "arxiv"
    assert len(p.authors) == 2


def test_paper_to_api_dict():
    p = Paper(
        paper_id="123",
        title="Test",
        authors=["Alice", "Bob"],
        published_date=datetime(2021, 1, 1),
    )
    d = p.to_api_dict()
    assert d["authors"] == "Alice; Bob"
    assert d["published_date"] == "2021-01-01T00:00:00"
    assert d["doi"] == ""


def test_search_result():
    sr = SearchResult(query="test", sources_requested="all")
    assert sr.total == 0
    assert sr.papers == []


def test_snowball_result():
    sb = SnowballResult(seed_paper_id="abc", direction="both", depth=1)
    assert sb.errors == []
