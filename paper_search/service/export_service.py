"""Export papers to CSV, RIS, or BibTeX formats."""

from __future__ import annotations

import csv
import os
import re
from typing import Any, Dict, List, Optional

from paper_search.models.paper import Paper


class ExportService:
    """Export a collection of papers to various bibliography formats."""

    def export(
        self,
        papers: List[Paper],
        format: str = "csv",
        save_path: str = "./exports",
        filename: str = "papers",
    ) -> str:
        """Export Pydantic Paper objects.

        Converts each Paper to a flat dict via ``to_api_dict()`` then delegates
        to the shared ``_do_export`` implementation.
        """
        dicts = [p.to_api_dict() for p in papers]
        return self._do_export(dicts, format, save_path, filename)

    def export_from_dicts(
        self,
        papers: List[Dict[str, Any]],
        format: str = "csv",
        save_path: str = "./exports",
        filename: str = "papers",
    ) -> str:
        """Export raw dicts (e.g. from MCP tool input).

        Accepts the same dict shape that ``Paper.to_api_dict()`` produces,
        where *authors* and *keywords* are ``"; "``-separated strings.
        """
        return self._do_export(papers, format, save_path, filename)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_export(
        self,
        papers: List[Dict[str, Any]],
        format: str,
        save_path: str,
        filename: str,
    ) -> str:
        os.makedirs(save_path, exist_ok=True)
        fmt = format.strip().lower()

        if fmt == "csv":
            return self._export_csv(papers, save_path, filename)
        elif fmt == "ris":
            return self._export_ris(papers, save_path, filename)
        elif fmt == "bibtex":
            return self._export_bibtex(papers, save_path, filename)
        else:
            return f"Unsupported format '{fmt}'. Use 'csv', 'ris', or 'bibtex'."

    # --- CSV --------------------------------------------------------

    @staticmethod
    def _export_csv(
        papers: List[Dict[str, Any]], save_path: str, filename: str
    ) -> str:
        out_path = os.path.join(save_path, f"{filename}.csv")
        fieldnames = [
            "title",
            "authors",
            "published_date",
            "doi",
            "abstract",
            "source",
            "citations",
            "url",
            "pdf_url",
            "categories",
            "keywords",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for p in papers:
                writer.writerow(p)
        return out_path

    # --- RIS --------------------------------------------------------

    @staticmethod
    def _export_ris(
        papers: List[Dict[str, Any]], save_path: str, filename: str
    ) -> str:
        out_path = os.path.join(save_path, f"{filename}.ris")
        lines: List[str] = []
        for p in papers:
            lines.append("TY  - JOUR")
            lines.append(f"TI  - {p.get('title', '')}")
            for author in (p.get("authors") or "").split("; "):
                if author.strip():
                    lines.append(f"AU  - {author.strip()}")
            if p.get("published_date"):
                date_str = str(p["published_date"])[:10].replace("-", "/")
                lines.append(f"PY  - {date_str}")
            if p.get("doi"):
                lines.append(f"DO  - {p['doi']}")
            if p.get("abstract"):
                lines.append(f"AB  - {p['abstract']}")
            if p.get("url"):
                lines.append(f"UR  - {p['url']}")
            if p.get("keywords"):
                for kw in str(p["keywords"]).split("; "):
                    if kw.strip():
                        lines.append(f"KW  - {kw.strip()}")
            lines.append("ER  - ")
            lines.append("")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return out_path

    # --- BibTeX -----------------------------------------------------

    @staticmethod
    def _export_bibtex(
        papers: List[Dict[str, Any]], save_path: str, filename: str
    ) -> str:
        out_path = os.path.join(save_path, f"{filename}.bib")
        entries: List[str] = []
        for i, p in enumerate(papers):
            first_author = (
                (p.get("authors") or "unknown").split(";")[0].split(",")[0].strip()
            )
            year = str(p.get("published_date", ""))[:4] or "nd"
            cite_key = re.sub(r"[^a-zA-Z0-9]", "", first_author).lower() + year + str(i)
            entry_lines = [f"@article{{{cite_key},"]
            entry_lines.append(f"  title = {{{p.get('title', '')}}},")
            entry_lines.append(
                f"  author = {{{(p.get('authors') or '').replace('; ', ' and ')}}},",
            )
            if p.get("published_date"):
                entry_lines.append(f"  year = {{{str(p['published_date'])[:4]}}},")
            if p.get("doi"):
                entry_lines.append(f"  doi = {{{p['doi']}}},")
            if p.get("abstract"):
                abstract_clean = p["abstract"].replace("{", "").replace("}", "")
                entry_lines.append(f"  abstract = {{{abstract_clean}}},")
            if p.get("url"):
                entry_lines.append(f"  url = {{{p['url']}}},")
            entry_lines.append("}")
            entries.append("\n".join(entry_lines))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(entries))
        return out_path
