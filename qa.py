"""Question answering over retrieved page-level evidence."""
from __future__ import annotations

from .llm_adapter import LLMUnavailable, OpenAICompatibleAdapter
from .pdf_parser import TextChunk
from .retrieval import PaperRetriever

LOW_EVIDENCE_MESSAGE = "The paper text available here does not provide enough evidence to answer this confidently."


def answer_question(question: str, chunks: list[TextChunk], adapter: OpenAICompatibleAdapter | None = None, use_embeddings: bool = True) -> dict[str, object]:
    retriever = PaperRetriever(chunks, use_embeddings=use_embeddings)
    retrieved = retriever.search(question, top_k=5)
    if not retrieved or retrieved[0][1] < 0.10:
        return {"answer": LOW_EVIDENCE_MESSAGE, "confidence": "low", "evidence": [], "retrieval_mode": retriever.mode}
    evidence = [{"page": c.page_number, "text": c.text, "score": round(score, 3)} for c, score in retrieved]
    llm_error = None
    if adapter is not None and adapter.available:
        try:
            result = adapter.answer(question, evidence)
            return {**result, "evidence": evidence, "retrieval_mode": retriever.mode}
        except LLMUnavailable as exc:
            llm_error = str(exc)
    excerpts = "\n\n".join(f'“{item["text"][:1000]}”' for item in evidence[:2])
    answer = "The most relevant text located in the paper is:\n\n" + excerpts
    return {"answer": answer, "confidence": "medium" if evidence else "low", "evidence": evidence, "retrieval_mode": retriever.mode, "llm_error": llm_error}
