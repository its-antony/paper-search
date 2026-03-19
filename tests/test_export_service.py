import os
import pytest
from paper_search.service.export_service import ExportService
from paper_search.models.paper import Paper

@pytest.fixture
def sample_papers():
    return [
        Paper(paper_id="1", title="Paper A", authors=["Alice"], doi="10.1/a"),
        Paper(paper_id="2", title="Paper B", authors=["Bob", "Carol"]),
    ]

def test_export_csv(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="csv", save_path=str(tmp_path))
    assert path.endswith(".csv")
    assert os.path.exists(path)

def test_export_ris(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="ris", save_path=str(tmp_path))
    assert path.endswith(".ris")
    assert os.path.exists(path)

def test_export_bibtex(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="bibtex", save_path=str(tmp_path))
    assert path.endswith(".bib")
    assert os.path.exists(path)

def test_export_unsupported_format(sample_papers, tmp_path):
    svc = ExportService()
    result = svc.export(sample_papers, format="xml", save_path=str(tmp_path))
    assert "unsupported" in result.lower()
