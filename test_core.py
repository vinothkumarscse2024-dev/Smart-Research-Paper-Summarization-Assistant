from __future__ import annotations

import hashlib

import fitz
import pytest

from research_assistant.database import PaperStore
from research_assistant.exporter import summary_to_markdown
from research_assistant.pdf_parser import PDFProcessingError, parse_pdf
from research_assistant.qa import answer_question
from research_assistant.retrieval import PaperRetriever
from research_assistant.sections import detect_sections, extractive_summary


def make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "A Practical Research Study", fontsize=16)
    page.insert_text((72, 110), "Abstract", fontsize=12)
    page.insert_text((72, 130), "We evaluate a new approach on the OpenData benchmark. The method improves accuracy.", fontsize=10)
    page.insert_text((72, 170), "Introduction", fontsize=12)
    page.insert_text((72, 190), "This study addresses efficient classification for small datasets.", fontsize=10)
    page.insert_text((72, 230), "Methods", fontsize=12)
    page.insert_text((72, 250), "We used a convolutional neural network and a held-out test set.", fontsize=10)
    page.insert_text((72, 290), "Results", fontsize=12)
    page.insert_text((72, 310), "The proposed model achieved 91% accuracy on the OpenData benchmark.", fontsize=10)
    page.insert_text((72, 350), "References", fontsize=12)
    page.insert_text((72, 370), "[1] Example Reference.", fontsize=10)
    output = doc.tobytes()
    doc.close()
    return output


def parse_fixture():
    return parse_pdf(make_pdf(), "example-study.pdf")


def test_extracts_metadata_pages_and_chunks():
    paper = parse_fixture()
    assert paper.page_count == 1
    assert paper.pages[0].page_number == 1
    assert "91% accuracy" in paper.full_text
    assert paper.chunks
    assert paper.title == "example study"


def test_rejects_invalid_and_scanned_pdf():
    with pytest.raises(PDFProcessingError, match="not a valid PDF"):
        parse_pdf(b"not a pdf")
    doc = fitz.open()
    doc.new_page()
    blank = doc.tobytes()
    doc.close()
    with pytest.raises(PDFProcessingError, match="No usable text"):
        parse_pdf(blank)


def test_detects_sections_and_extractive_summary_marks_missing():
    paper = parse_fixture()
    sections = detect_sections(paper.pages)
    assert {"Abstract", "Introduction", "Methods", "Results", "References"}.issubset(sections)
    summary = extractive_summary(sections, paper.full_text)
    assert "91% accuracy" in summary["Key findings"]
    assert summary["Limitations"].startswith("Not explicitly")


def test_retrieval_and_qa_return_page_evidence():
    paper = parse_fixture()
    chunks = list(paper.chunks)
    retrieved = PaperRetriever(chunks, use_embeddings=False).search("what accuracy result did model achieve", top_k=2)
    assert retrieved
    result = answer_question("what accuracy result did model achieve", chunks, adapter=None, use_embeddings=False)
    assert result["evidence"]
    assert result["evidence"][0]["page"] == 1
    assert "accuracy" in result["answer"].lower()


def test_qa_reports_missing_evidence():
    paper = parse_fixture()
    result = answer_question("Which hospital was used for the clinical trial?", list(paper.chunks), adapter=None, use_embeddings=False)
    assert result["confidence"] == "low"
    assert not result["evidence"]
    assert "not provide enough evidence" in result["answer"]


def test_sqlite_save_update_delete_and_markdown_export(tmp_path):
    paper = parse_fixture()
    sections = detect_sections(paper.pages)
    summary = extractive_summary(sections, paper.full_text)
    store = PaperStore(tmp_path / "papers.db")
    fingerprint = hashlib.sha256(make_pdf()).hexdigest()
    paper_id = store.save_paper(fingerprint, "example-study.pdf", paper, sections, summary, "ML, demo", "Read later")
    record = store.get_paper(paper_id)
    assert record and record["chunks"]
    assert record["tags"] == "ML, demo"
    assert "Key findings" in summary_to_markdown(record)
    with pytest.raises(ValueError, match="already been added"):
        store.save_paper(fingerprint, "example-study.pdf", paper, sections, summary)
    store.update_details(paper_id, "updated", "checked")
    assert store.get_paper(paper_id)["notes"] == "checked"
    assert len(store.list_papers()) == 1
    store.delete_paper(paper_id)
    assert store.get_paper(paper_id) is None
    assert store.search_chunks(paper_id) == []
