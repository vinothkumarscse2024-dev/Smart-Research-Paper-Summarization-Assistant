from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from research_assistant.database import PaperStore
from research_assistant.exporter import summary_to_markdown
from research_assistant.llm_adapter import LLMUnavailable, OpenAICompatibleAdapter
from research_assistant.pdf_parser import PDFProcessingError, TextChunk, parse_pdf
from research_assistant.qa import answer_question
from research_assistant.sections import detect_sections, extractive_summary

load_dotenv()

st.set_page_config(page_title="Paperwise | Research Assistant", page_icon="📚", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#172b3a; --muted:#667988; --teal:#127c75; --line:#e2e9eb; --wash:#f4f8f8; }
html, body, [class*="css"] { font-family:'DM Sans', sans-serif; color:var(--ink); }
h1,h2,h3 { font-family:'Manrope',sans-serif; letter-spacing:-.03em; }
.block-container { max-width:1320px; padding-top:2rem; padding-bottom:4rem; }
[data-testid="stSidebar"] { background:#f4f8f8; border-right:1px solid var(--line); }
.hero { padding:1.7rem 1.9rem; border-radius:18px; background:linear-gradient(115deg,#10394a 0%,#176e70 68%,#63a99a 100%); color:white; margin-bottom:1.25rem; }
.hero h1 { color:white; font-size:2rem; margin:0 0 .4rem; }
.hero p { color:#e1eeee; margin:0; font-size:1rem; }
.info-card { background:#fff; border:1px solid var(--line); padding:1rem 1.1rem; border-radius:14px; height:100%; }
.info-card .label { color:var(--muted); font-size:.82rem; }
.info-card .value { font-family:'Manrope',sans-serif; font-size:1.4rem; font-weight:700; color:var(--ink); margin-top:.2rem; }
.subtle { color:var(--muted); }
.citation { background:#f5f8f8; border-left:3px solid #19847a; border-radius:4px; padding:.8rem 1rem; margin:.5rem 0; color:#304750; }
.stButton>button[kind="primary"] { background:#127c75; border-color:#127c75; }
hr { border-color:var(--line); }
</style>
""", unsafe_allow_html=True)

DB_PATH = os.getenv("PAPER_DB_PATH", "data/papers.db")
store = PaperStore(DB_PATH)
llm = OpenAICompatibleAdapter()


def metric_card(label: str, value: str | int) -> None:
    st.markdown(f'<div class="info-card"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)


def show_summary(summary: dict[str, str]) -> None:
    for field, value in summary.items():
        with st.expander(field, expanded=field in {"Abstract", "Key findings"}):
            st.write(value)


def process_upload(uploaded_file, tags: str, notes: str) -> int:
    raw = uploaded_file.getvalue()
    fingerprint = hashlib.sha256(raw).hexdigest()
    paper = parse_pdf(raw, uploaded_file.name)
    sections = detect_sections(paper.pages)
    summary = extractive_summary(sections, paper.full_text)
    if llm.available:
        try:
            summary = llm.summarize(sections, paper.full_text)
        except LLMUnavailable as exc:
            st.warning(f"AI summary was unavailable; saved the extractive summary instead. Details: {exc}")
    return store.save_paper(fingerprint, uploaded_file.name, paper, sections, summary, tags, notes)


with st.sidebar:
    st.markdown("## Paperwise")
    st.caption("A careful reading companion for research papers")
    page = st.radio("Workspace", ["Library", "Add papers", "About"], label_visibility="collapsed", key="nav_page")
    st.divider()
    st.markdown("**Analysis mode**")
    if llm.available:
        st.success(f"AI adapter enabled · `{llm.model}`")
        st.caption("Your API key stays in your local environment.")
    else:
        st.info("Local extractive mode")
        st.caption("Configure an API key to enable LLM summaries and answers.")
    st.caption("PDF text is processed locally unless an external API is configured.")

if page == "Add papers":
    st.markdown('<div class="hero"><h1>Add research papers</h1><p>Upload searchable PDFs to extract text, detect sections, and create a structured, evidence-aware summary.</p></div>', unsafe_allow_html=True)
    st.info("Scanned PDFs without an embedded text layer are not OCR-processed. Your original PDF is not stored; extracted text and page-level passages are stored in the local SQLite library.")
    uploaded_files = st.file_uploader("Choose one or more research papers", type=["pdf"], accept_multiple_files=True, help="PDF files only. Password-protected or image-only PDFs will be rejected with an explanation.")
    col1, col2 = st.columns(2)
    tags = col1.text_input("Tags (comma-separated)", placeholder="e.g. NLP, healthcare, review")
    notes = col2.text_input("Initial notes", placeholder="Optional private reading notes")
    if st.button("Process selected PDFs", type="primary", disabled=not uploaded_files):
        for file in uploaded_files:
            with st.status(f"Processing {file.name}…", expanded=True) as status:
                try:
                    paper_id = process_upload(file, tags, notes)
                    status.update(label=f"Added: {file.name}", state="complete")
                    st.success(f"Saved as paper #{paper_id}")
                except PDFProcessingError as exc:
                    status.update(label=f"Could not process {file.name}", state="error")
                    st.error(str(exc))
                except ValueError as exc:
                    status.update(label=f"Could not add {file.name}", state="error")
                    st.warning(str(exc))
                except Exception as exc:
                    status.update(label=f"Unexpected processing error for {file.name}", state="error")
                    st.error(f"{type(exc).__name__}: {exc}")

elif page == "About":
    st.markdown('<div class="hero"><h1>About Paperwise</h1><p>Research-paper organization and evidence-grounded exploration, with clear boundaries around what the source actually says.</p></div>', unsafe_allow_html=True)
    st.markdown("### What it does")
    st.markdown("Uploads text-based research PDFs; extracts metadata, page text, and passages; detects common paper sections; summarizes key research dimensions; answers questions against retrieved evidence; stores tags and notes locally in SQLite; exports summaries as Markdown; and supports deleting saved records.")
    st.markdown("### AI and privacy")
    st.markdown("Without an API key, summaries are extractive and question answers show relevant source passages. With `OPENAI_API_KEY`, the app can request grounded structured summaries and answers from the configured OpenAI-compatible API. Only extracted text and retrieved excerpts are sent to that API. AI-generated content can still be incomplete or wrong; always verify against the linked page evidence. This app does not claim to validate scientific truth.")
    st.markdown("### Limitations")
    st.markdown("Section detection relies on common textual headings and can miss unusual layouts. PDFs must contain selectable text; OCR, tables, equations, and figure interpretation are not implemented. Page references use physical PDF page numbers. Embedding retrieval uses Sentence Transformers when the model is installed and available; otherwise a local keyword-overlap retriever is used.")

else:
    papers = store.list_papers()
    st.markdown('<div class="hero"><h1>Your research library</h1><p>Search, summarize, and ask source-grounded questions across your saved papers.</p></div>', unsafe_allow_html=True)
    total_pages = sum(p["page_count"] for p in papers)
    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Saved papers", len(papers))
    with c2: metric_card("Total pages", total_pages)
    with c3: metric_card("AI assistance", "On" if llm.available else "Optional")
    if not papers:
        st.markdown("### Start with a paper")
        st.write("Your local library is empty. Add a PDF to create your first evidence-grounded summary.")
        if st.button("Go to Add papers", type="primary"):
            st.session_state["nav_page"] = "Add papers"
            st.rerun()
    else:
        st.markdown("### Saved papers")
        query = st.text_input("Filter by title, author, filename, or tag", placeholder="Search your library")
        filtered = [p for p in papers if query.lower() in " ".join(str(p[k] or "") for k in ("title", "author", "filename", "tags")).lower()]
        labels = {f"{p['title']}  ·  {p['author'] or p['filename']}  ·  {p['page_count']} pages  ·  #{p['id']}": p["id"] for p in filtered}
        if not labels:
            st.warning("No papers match that search.")
        else:
            selected_label = st.selectbox("Select a paper", labels.keys())
            paper_id = labels[selected_label]
            record = store.get_paper(paper_id)
            if record:
                left, right = st.columns([2, 1])
                with left:
                    st.markdown(f"## {record['title']}")
                    st.caption(f"{record['filename']} · {record['page_count']} pages · {record['author'] or 'Author metadata unavailable'}")
                    show_summary(record["summary"])
                with right:
                    st.markdown("### Paper details")
                    with st.form(f"details-{paper_id}"):
                        edited_tags = st.text_input("Tags", value=record["tags"])
                        edited_notes = st.text_area("Notes", value=record["notes"], height=170)
                        if st.form_submit_button("Save details"):
                            store.update_details(paper_id, edited_tags, edited_notes)
                            st.success("Paper details saved.")
                            st.rerun()
                    st.download_button("Export summary (.md)", summary_to_markdown(record), file_name=f"paper-{paper_id}-summary.md", mime="text/markdown", use_container_width=True)
                    with st.expander("Detected sections"):
                        if record["sections"]:
                            for section_name, section_data in record["sections"].items():
                                st.markdown(f"**{section_name}** · pp. {section_data.get('start_page')}–{section_data.get('end_page')}")
                        else:
                            st.write("No standard section headings were detected.")
                    with st.expander("Delete paper", expanded=False):
                        st.warning("This removes the saved text, summary, and metadata from the local database. The original PDF is not stored.")
                        if st.button("Delete this paper", key=f"delete-{paper_id}"):
                            store.delete_paper(paper_id)
                            st.success("Paper deleted.")
                            st.rerun()
                st.divider()
                st.markdown("### Ask this paper")
                st.caption("Answers are tied to retrieved passages and PDF page numbers. Missing evidence is called out rather than guessed.")
                with st.form(f"question-{paper_id}"):
                    question = st.text_input("Your question", placeholder="What dataset and evaluation metrics were used?")
                    ask = st.form_submit_button("Find evidence", type="primary")
                if ask and question.strip():
                    chunks = [TextChunk(int(c["chunk_id"]), int(c["page_number"]), c["text"]) for c in record["chunks"]]
                    with st.spinner("Retrieving evidence and drafting an answer…"):
                        answer = answer_question(question, chunks, llm)
                    confidence = answer["confidence"].capitalize()
                    st.markdown(f"**Confidence: {confidence}** · Retrieval: `{answer['retrieval_mode']}`")
                    st.write(answer["answer"])
                    if answer.get("llm_error"):
                        st.caption(f"The AI service was not available; showing locally retrieved evidence. {answer['llm_error']}")
                    if answer["evidence"]:
                        with st.expander(f"Evidence references ({len(answer['evidence'])})", expanded=True):
                            for index, source in enumerate(answer["evidence"], 1):
                                st.markdown(f"**[{index}] PDF page {source['page']}** · relevance {source['score']}")
                                st.markdown(f'<div class="citation">{source["text"]}</div>', unsafe_allow_html=True)
                            st.caption("Page numbers refer to the physical page positions in the uploaded PDF. Confirm context in the original paper.")
                    else:
                        st.warning("No relevant passage was retrieved. Try different wording or check whether this topic appears in the extracted text.")
