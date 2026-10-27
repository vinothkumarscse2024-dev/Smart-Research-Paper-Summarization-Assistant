# Smart Research Paper Summarization Assistant

A modular Streamlit application for organizing research PDFs, generating structured summaries, and asking questions with page-level evidence. Built as a college engineering project with local SQLite persistence and an optional OpenAI-compatible LLM adapter.

> **Uploaded requirements PDF:** No PDF attachment was available in the project workspace during implementation. This version follows the requirements listed in the user message. Please compare against the source PDF and add any omitted document-specific requirements before submission.

## Features

- Upload one or several text-based research papers in PDF format.
- Extract PDF metadata, page count, page text, and source passages using PyMuPDF.
- Segment sentences with NLTK's built-in Punkt tokenizer without requiring downloaded language data.
- Detect common headings: Abstract, Introduction, Methods, Results, Discussion, Conclusion, Limitations, and References.
- Generate structured summaries for abstract, research problem, methodology, datasets, evaluation metrics, findings, limitations, and conclusion.
- Ask questions about an individual paper; retrieve relevant passages and display PDF page numbers as evidence.
- Signal weak/missing evidence. No-answer outcomes do not fabricate facts or citations.
- Store papers, summaries, tags, notes, extracted text, and chunks in local SQLite (`data/papers.db` by default).
- Edit tags/notes, export Markdown summaries, filter the library, and delete saved records.
- Gracefully reject invalid, empty, encrypted, or textless/scanned PDFs (OCR is not included).
- Basic automated tests for extraction, sections, retrieval, persistence, exports, and failure paths.

## Project structure

```text
smart-research-paper-summarization-assistant/
├── app.py
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── src/research_assistant/
│   ├── database.py
│   ├── exporter.py
│   ├── llm_adapter.py
│   ├── pdf_parser.py
│   ├── qa.py
│   ├── retrieval.py
│   └── sections.py
└── tests/
```

## Requirements

- Python 3.10 or newer (Python 3.11 is a good Windows choice).
- Windows 10, macOS, or Linux.
- Internet access during dependency installation. Sentence Transformers may download its embedding model on first use; the app falls back to local keyword retrieval if the model cannot load.
- Optional: an API key for an OpenAI-compatible chat completions endpoint. Core upload, database, extractive summary, and evidence retrieval work without an API key.

## Install and run on Windows 10

1. Install Python 3.11 from [python.org](https://www.python.org/downloads/). In the installer, check **Add Python to PATH**. Open PowerShell and verify:

   ```powershell
   py --version
   ```

2. Download or clone this repository, then move into its folder:

   ```powershell
   cd C:\path\to\smart-research-paper-summarization-assistant
   ```

3. Create and activate a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. Or skip activation and use `.venv\Scripts\python.exe` for each command.

4. Install packages:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e .
   ```

5. (Optional) Enable AI summaries and generated answers. Copy the template and edit it:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Add your key to `OPENAI_API_KEY=...`; keep `.env` private and never commit it. The adapter supports OpenAI-compatible APIs through `OPENAI_BASE_URL` and `OPENAI_MODEL`. If omitted, it uses the OpenAI base URL and `gpt-4o-mini`. Usage may incur provider charges. Without a key, the app uses extractive summaries and quotes retrieved source passages instead of making up an LLM answer.

6. Launch the app:

   ```powershell
   streamlit run app.py
   ```

   Streamlit prints a local URL (typically `http://localhost:8501`). Open it in a browser. Upload a searchable PDF on **Add papers**, then select it in **Library**.

## Run tests

From the project root (with the venv activated):

```powershell
python -m pytest -q
```

The tests do not call an external API or download an embedding model.

## Optional settings

Set these in `.env` or the shell before launch:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Enables calls to the configured LLM endpoint |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat-completions model name |
| `PAPER_DB_PATH` | `data/papers.db` | Local SQLite database path |

### What uses an external AI API?

Only the optional generation of LLM-based structured summaries and LLM-written answers send paper text to the configured chat API. For summaries, extracted text is capped to the first 50,000 characters; for QA, only top retrieved evidence passages are sent. API providers process requests under their own policies and may charge fees. With no key, the entire core workflow runs locally (PyMuPDF extraction, simple extractive summaries, keyword retrieval, SQLite, and evidence display). Sentence Transformer embeddings, when available, run locally after model download.

## Safety, evidence, and limitations

- AI-generated answers and summaries are not guaranteed to be correct. Verify them against the PDF.
- The app renders page references from extracted passages; it does not verify the paper's scientific validity.
- Scanned-image PDFs, complex multi-column layouts, tables, mathematical notation, citations, and figures can extract poorly. OCR, table parsing, and visual figure analysis are not implemented.
- Heading detection uses common text labels and may miss headings with unusual formatting or titles.
- Summary fields absent from detected text explicitly say they are not stated; extracted snippets may still be incomplete.
- The original PDF file is **not** retained. Extracted page text, metadata, summary, tags, notes, and chunks are saved locally in SQLite. Back up `data/papers.db` if needed.
- The SQLite database may contain copyrighted paper text. Keep it private and follow your institution's and the paper publisher's terms. Do not upload `data/` to GitHub.

## Upload the project to GitHub (Windows 10)

1. Create a new **empty** repository on [GitHub](https://github.com/new), such as `smart-research-paper-summarization-assistant`. Do not initialize it with a README if you plan to push this folder as-is.
2. Install Git for Windows if needed. In PowerShell, go to the project directory and confirm `.env` is ignored:

   ```powershell
   git status --short
   ```

   Never commit API keys, your `.env`, the local database, uploaded papers, or your virtual environment.

3. Initialize and commit:

   ```powershell
   git init
   git add .
   git status
   git commit -m "Initial research paper summarization assistant"
   ```

4. Set the remote URL from the new GitHub repository and push (replace `YOUR-USERNAME`):

   ```powershell
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/smart-research-paper-summarization-assistant.git
   git push -u origin main
   ```

5. If prompted, authenticate with a GitHub browser sign-in or a Personal Access Token; do not put a token in the repository or source code. Refresh the repository page to confirm the files appear.

## Suggested engineering-project demo

1. Launch the app without an API key to demonstrate privacy-friendly local mode.
2. Upload a text-based research PDF, add tags and notes, and inspect detected sections.
3. Ask a question that is answered in the paper and open its page references.
4. Ask about information absent from the paper and show the low-evidence response.
5. Export the summary, edit its notes, delete the record, and run the tests.

## License

MIT. See `LICENSE`.
