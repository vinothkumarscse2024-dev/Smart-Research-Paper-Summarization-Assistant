"""Export a saved paper summary as Markdown."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def summary_to_markdown(paper: dict[str, Any]) -> str:
    lines = [f"# {paper.get('title') or paper.get('filename') or 'Research paper summary'}", "", f"- **File:** {paper.get('filename', 'Unknown')}", f"- **Author:** {paper.get('author') or 'Not available in PDF metadata'}", f"- **Pages:** {paper.get('page_count', 'Unknown')}", f"- **Exported:** {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}", ""]
    if paper.get("tags"):
        lines.extend([f"- **Tags:** {paper['tags']}", ""])
    for key, value in paper.get("summary", {}).items():
        lines.extend([f"## {key}", "", str(value), ""])
    if paper.get("notes"):
        lines.extend(["## User notes", "", str(paper["notes"]), ""])
    lines.extend(["---", "Generated from text extracted from the uploaded PDF. Verify claims against the paper; unavailable information is not inferred.", ""])
    return "\n".join(lines)
