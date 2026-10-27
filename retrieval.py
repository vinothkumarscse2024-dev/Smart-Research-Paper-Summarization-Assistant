"""Evidence retrieval with Sentence Transformers and a deterministic local fallback."""
from __future__ import annotations

import re
from collections import Counter
from typing import Sequence

from .pdf_parser import TextChunk

_STOP = set("a an and are as at be by for from has have in into is it of on or that the their this to was were will with what which who when where why how about does did can could would should use used using".split())


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


class PaperRetriever:
    """Encodes chunks lazily when possible; always remains usable without network/model install."""
    def __init__(self, chunks: Sequence[TextChunk], use_embeddings: bool = True):
        self.chunks = list(chunks)
        self._model = None
        self._vectors = None
        self.mode = "keyword"
        if use_embeddings and self.chunks:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                self._vectors = self._model.encode([c.text for c in self.chunks], normalize_embeddings=True, show_progress_bar=False)
                self.mode = "sentence-transformers"
            except Exception:
                self._model = None
                self._vectors = None

    def search(self, query: str, top_k: int = 5) -> list[tuple[TextChunk, float]]:
        if not query.strip() or not self.chunks:
            return []
        if self._model is not None and self._vectors is not None:
            q = self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            scores = self._vectors @ q
            ranked = sorted(enumerate(scores), key=lambda pair: float(pair[1]), reverse=True)
            return [(self.chunks[i], float(score)) for i, score in ranked[:top_k] if float(score) > 0.08]
        query_terms = Counter(_tokens(query))
        scored: list[tuple[TextChunk, float]] = []
        for chunk in self.chunks:
            terms = Counter(_tokens(chunk.text))
            overlap = sum(min(count, terms[token]) for token, count in query_terms.items())
            coverage = overlap / max(1, sum(query_terms.values()))
            if overlap:
                scored.append((chunk, coverage + min(overlap, 5) * 0.015))
        return sorted(scored, key=lambda pair: pair[1], reverse=True)[:top_k]
