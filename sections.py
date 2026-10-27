"""Section heading detection and conservative extractive summary helpers."""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Iterable

from .pdf_parser import PageText

SECTION_ALIASES = OrderedDict([
    ("Abstract", ["abstract", "summary"]),
    ("Introduction", ["introduction", "background", "motivation"]),
    ("Methods", ["methods", "methodology", "materials and methods", "experimental setup", "approach"]),
    ("Results", ["results", "experiments", "experimental results", "evaluation"]),
    ("Discussion", ["discussion", "analysis"]),
    ("Conclusion", ["conclusion", "conclusions", "concluding remarks"]),
    ("Limitations", ["limitations", "threats to validity"]),
    ("References", ["references", "bibliography"]),
])

_HEADING_RE = re.compile(r"^\s*(?:(?:\d+(?:\.\d+)*|[IVXLC]+)[.)]?\s+)?([A-Za-z][A-Za-z &:/-]{1,60})\s*[:.]?\s*$")


def _canonical_heading(line: str) -> str | None:
    match = _HEADING_RE.match(line.strip())
    if not match:
        return None
    normalized = re.sub(r"\s+", " ", match.group(1).strip().lower())
    normalized = re.sub(r"\s*[:/]\s*", " ", normalized)
    for canonical, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def detect_sections(pages: Iterable[PageText]) -> dict[str, dict[str, object]]:
    """Return recognized section text and inclusive page range; absent sections are omitted."""
    found: dict[str, dict[str, object]] = {}
    current: str | None = None
    for page in pages:
        for line in page.text.splitlines():
            heading = _canonical_heading(line)
            if heading:
                current = heading
                if heading not in found:
                    found[heading] = {"text": "", "start_page": page.page_number, "end_page": page.page_number}
                continue
            if current and line.strip():
                item = found[current]
                item["text"] = (str(item["text"]) + " " + line.strip()).strip()
                item["end_page"] = page.page_number
    return found


def sentences(text: str) -> list[str]:
    try:
        # This tokenizer ships with NLTK and does not need downloaded language data.
        from nltk.tokenize import PunktSentenceTokenizer
        return [s.strip() for s in PunktSentenceTokenizer().tokenize(text) if s.strip()]
    except ImportError:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if s.strip()]


def _first_sentences(section: dict[str, object] | None, limit: int = 3) -> str:
    if not section or not str(section.get("text", "")).strip():
        return "Not explicitly identified in the extracted text."
    return " ".join(sentences(str(section["text"]))[:limit]) or str(section["text"])[:650]


def extractive_summary(sections: dict[str, dict[str, object]], full_text: str) -> dict[str, str]:
    """Build a transparent, extractive baseline; do not fill absent scientific claims."""
    intro = sections.get("Introduction")
    methods = sections.get("Methods")
    results = sections.get("Results")
    discussion = sections.get("Discussion")
    conclusion = sections.get("Conclusion")
    abstract = sections.get("Abstract")
    limit = sections.get("Limitations")
    method_text = _first_sentences(methods, 3)
    result_text = _first_sentences(results, 3)
    discussion_text = _first_sentences(discussion, 2)
    limitations_text = _first_sentences(limit, 2)
    if limitations_text.startswith("Not explicitly") and discussion:
        hits = [s for s in sentences(str(discussion.get("text", ""))) if re.search(r"\blimitations?|future work|threats to validity\b", s, re.I)]
        if hits:
            limitations_text = " ".join(hits[:2])
    return {
        "Abstract": _first_sentences(abstract, 4),
        "Research problem": _first_sentences(intro, 2),
        "Methodology": method_text,
        "Datasets": _evidence_sentences(full_text, r"\b(dataset|data set|corpus|benchmark|participants|samples?)\b"),
        "Evaluation metrics": _evidence_sentences(full_text, r"\b(accuracy|precision|recall|f1(?:-score)?|auc|bleu|rouge|rmse|mae|mse|perplexity|metric)\b"),
        "Key findings": result_text if not result_text.startswith("Not explicitly") else _first_sentences(conclusion, 3),
        "Limitations": limitations_text,
        "Conclusion": _first_sentences(conclusion, 2) if conclusion else discussion_text,
    }


def _evidence_sentences(text: str, pattern: str) -> str:
    matches = [s for s in sentences(" ".join(text.split())) if re.search(pattern, s, re.I)]
    if not matches:
        return "Not explicitly identified in the extracted text."
    return " ".join(matches[:3])
