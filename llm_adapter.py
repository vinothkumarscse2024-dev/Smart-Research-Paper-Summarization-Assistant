"""Optional OpenAI-compatible LLM calls. API credentials are read only from environment."""
from __future__ import annotations

import json
import os
from typing import Any

SUMMARY_KEYS = ["Abstract", "Research problem", "Methodology", "Datasets", "Evaluation metrics", "Key findings", "Limitations", "Conclusion"]


class LLMUnavailable(RuntimeError):
    pass


class OpenAICompatibleAdapter:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url if base_url is not None else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model if model is not None else os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def available(self) -> bool:
        return bool(self.api_key.strip())

    def _client(self):
        if not self.available:
            raise LLMUnavailable("No API key configured. Add OPENAI_API_KEY to your environment or .env file.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMUnavailable("Install the optional OpenAI client with: pip install openai") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _complete_json(self, system: str, user: str) -> dict[str, Any]:
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Model did not return a JSON object")
            return result
        except LLMUnavailable:
            raise
        except Exception as exc:
            raise LLMUnavailable(f"LLM request failed: {exc}") from exc

    def summarize(self, sections: dict[str, dict[str, object]], text: str) -> dict[str, str]:
        source = text[:50_000]
        result = self._complete_json(
            "You summarize research papers faithfully. Use only the source text. Do not infer missing facts or fabricate results, datasets, methods, limitations, or citations. For unavailable information return exactly 'Not explicitly stated in the paper text.' Return JSON with these string keys: " + ", ".join(SUMMARY_KEYS),
            "Detected sections (may be incomplete): " + json.dumps(sections, ensure_ascii=False) + "\n\nPaper text:\n" + source,
        )
        return {key: str(result.get(key, "Not explicitly stated in the paper text.")) for key in SUMMARY_KEYS}

    def answer(self, question: str, evidence: list[dict[str, object]]) -> dict[str, str]:
        result = self._complete_json(
            "Answer the question using only the supplied excerpts. If the excerpts do not support an answer, say 'The paper text available here does not provide enough evidence to answer this confidently.' Never invent facts, citations, or page numbers. Return JSON keys answer and confidence, where confidence is high, medium, or low.",
            "Question: " + question + "\nEvidence excerpts with source page numbers:\n" + json.dumps(evidence, ensure_ascii=False),
        )
        confidence = str(result.get("confidence", "low")).lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        return {"answer": str(result.get("answer", "The paper text available here does not provide enough evidence to answer this confidently.")), "confidence": confidence}
