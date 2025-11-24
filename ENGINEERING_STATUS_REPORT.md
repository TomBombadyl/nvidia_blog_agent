# ENGINEERING STATUS REPORT

## NVIDIA Tech Blog Intelligence Agent

**GCP Project:**

* Name: `nvidia-blog-agent`
* ID: `nvidia-blog-agent`
* Number: `262844214274`

**MCP Tools Available (for later integration):**

* `context7` – up-to-date documentation / context
* `cloud-run` – manage Cloud Run services
* `storage` – Cloud Storage access

**Current Test Status:**

* ✅ **118 tests passing** (Phases 1–6)

---

## 1. High-Level System Picture

End-to-end data flow (logical, not yet wired into a single ADK workflow):

1. **Discovery**
   `discover_posts_from_feed()` parses NVIDIA blog index HTML → `BlogPost` objects.
   `diff_new_posts()` filters **new** posts via stable `id` from `generate_post_id()`.

2. **Scraping**
   Async `fetch_and_parse_blog()` uses an abstract `HtmlFetcher` to fetch HTML, then `parse_blog_html()` → `RawBlogContent` (raw HTML, cleaned text, sections).

3. **Summarization (LLM / ADK)**
   `SummarizerAgent` (ADK LlmAgent) uses:

   * `build_summary_prompt(raw: RawBlogContent)` → prompt string.
   * LLM model (Gemini) → JSON summary.
   * `parse_summary_json()` → `BlogSummary`.

4. **RAG Ingestion**
   `HttpRagIngestClient` (implements `RagIngestClient`) sends `BlogSummary.to_rag_document()` and metadata via HTTP to `{base_url}/add_doc` for storage in a RAG backend (e.g., CA-RAG on Cloud Run).

5. **RAG Retrieval**
   `HttpRagRetrieveClient` (implements `RagRetrieveClient`) calls `{base_url}/query` → maps generic RAG results to `RetrievedDoc` objects.

6. **Q&A**
   `QAAgent`:

   * Uses `RagRetrieveClient` to get relevant `RetrievedDoc`s.
   * Uses a pluggable `QaModelLike` to generate grounded answers.
   * Returns `(answer_text, retrieved_docs)`.

What's missing (next phases): orchestration into ADK workflows (Watcher → Scraper → Summarizer → Ingestor) and context/memory/eval.

---

## 2. Current Project Structure

```text
nvidia_blog_agent/
  __init__.py

  contracts/
    __init__.py
    blog_models.py

  tools/
    __init__.py
    discovery.py         # Phase 2
    scraper.py           # Phase 3
    summarization.py     # Phase 4
    rag_ingest.py        # Phase 5
    rag_retrieve.py      # Phase 6

  agents/
    __init__.py
    summarizer_agent.py  # Phase 4
    qa_agent.py          # Phase 6

  context/
    __init__.py          # reserved for sessions/memory/compaction (Phase 8)

  eval/
    __init__.py          # reserved for eval harness (Phase 9)

tests/
  __init__.py
  conftest.py            # pytest path/bootstrap helpers

  unit/
    __init__.py
    test_contracts.py

    tools/
      __init__.py
      test_discovery_tool.py
      test_scraper_parser.py
      test_summarization.py
      test_rag_ingest_payloads.py
      test_rag_retrieval_payloads.py

    agents/
      __init__.py
      test_summarizer_agent.py
      test_qa_agent.py

  workflows/
    __init__.py          # reserved for Phase 7

  context/
    __init__.py          # reserved for Phase 8

  e2e/
    __init__.py          # reserved for Phase 9
```

---

## 3. Modules & Behavior (By Phase)

### Phase 1 – Contracts & Data Models ✅

**File:** `contracts/blog_models.py`

Models:

* `BlogPost`

  * `id: str` (SHA256 of URL via `generate_post_id()`, non-empty)
  * `url: HttpUrl`
  * `title: str`
  * `published_at: Optional[datetime]`
  * `tags: List[str]`
  * `source: str = "nvidia_tech_blog"`

* `RawBlogContent`

  * `blog_id: str`
  * `url: HttpUrl`
  * `title: str`
  * `html: str` – raw HTML
  * `text: str` – cleaned article text
  * `sections: List[str]`

* `BlogSummary`

  * `blog_id, title, url, published_at`
  * `executive_summary: str`
  * `technical_summary: str`
  * `bullet_points: List[str]`
  * `keywords: List[str]` (normalized to lowercase & deduped)

* `RetrievedDoc`

  * `blog_id, title, url`
  * `snippet: str`
  * `score: float` (validated into [0, 1])
  * `metadata: dict`

Utilities:

* `generate_post_id(url: str) -> str`
* `blog_summary_to_dict(summary: BlogSummary) -> dict`
* `BlogSummary.to_rag_document() -> str` – nicely formatted text doc for RAG ingestion.

**Tests:** `tests/unit/test_contracts.py` – 22 tests, strong coverage on validation + serialization.

---

### Phase 2 – Discovery Tools ✅

**File:** `tools/discovery.py`

* `diff_new_posts(existing_ids, discovered_posts) -> List[BlogPost]`

  * Set-based filtering, preserves original order, pure.

* `discover_posts_from_feed(raw_feed, default_source="nvidia_tech_blog") -> List[BlogPost]`

  * BeautifulSoup-based:

    * Looks for `div.post`, `article`, and fallback `<div>` patterns.
    * Extracts:

      * URL from `<a href>`.
      * Title from link text.
      * Optional `published_at` from `<time datetime>`.
      * Tags via `.tag` class.
  * Graceful degradation – skips malformed entries, returns empty list if nothing valid.

**Tests:** `tests/unit/tools/test_discovery_tool.py` – 20 tests, including ID stability, malformed HTML, datetime variants, tag extraction.

---

### Phase 3 – Scraper / HtmlFetcher Boundary ✅

**File:** `tools/scraper.py`

* `class HtmlFetcher(Protocol)`

  ```python
  async def fetch_html(self, url: str) -> str
  ```

* `parse_blog_html(blog: BlogPost, html: str) -> RawBlogContent`

  * Select article root using fallback order:

    1. `<article>`
    2. `div` with likely classes (`post`, `article`, `blog-article`, `content`, `main-content`)
    3. `<main>`
    4. `<body>`
  * Strip `<script>`, `<style>`, etc.
  * Normalize whitespace, output non-empty `text` (fallback to blog title if necessary).
  * Build `sections` by grouping paragraphs under headings (`h1`–`h6`); if no headings, one "full text" section.

* `async def fetch_and_parse_blog(blog: BlogPost, fetcher: HtmlFetcher) -> RawBlogContent`

  * Uses injected `fetcher` to get HTML, then `parse_blog_html`.

**Tests:** `tests/unit/tools/test_scraper_parser.py` – 14 tests (article present, fallbacks, no headings, script/style removal, whitespace normalization, FakeFetcher).

---

### Phase 4 – Summarization Helpers + SummarizerAgent ✅

**File:** `tools/summarization.py`

* `build_summary_prompt(raw: RawBlogContent, max_text_chars: int = 4000) -> str`

  * Constructs prompt including:

    * Title, URL.
    * Explanation of JSON output format:

      ```json
      {
        "executive_summary": "...",
        "technical_summary": "...",
        "bullet_points": ["..."],
        "keywords": ["..."]
      }
      ```
    * Truncated `raw.text` (and optionally sections) respecting `max_text_chars`.
  * Explicit instructions to return **strict JSON**; parsing functions robust to markdown fences / extra text.

* `parse_summary_json(raw, json_text, published_at=None) -> BlogSummary`

  * Handles:

    * Raw JSON.
    * JSON wrapped in markdown code blocks.
    * Leading/trailing commentary around JSON.
  * Validates required keys; defaults bullet_points/keywords to `[]` if missing.
  * Raises `ValueError` if JSON malformed or required keys missing.

**File:** `agents/summarizer_agent.py`

* `SummarizerAgent` (ADK LlmAgent-based pattern)

  * Reads `state["raw_contents"]` (list of `RawBlogContent` or dicts).
  * For each:

    * Uses `build_summary_prompt`.
    * Calls injected LLM/client.
    * Parses JSON with `parse_summary_json`.
    * Appends `BlogSummary` to `state["summaries"]`.
  * Designed for:

    * DI of real Gemini model in prod.
    * DI of stub model in tests.

* `SummarizerAgentStub`

  * Test-friendly stand-in, bypasses real ADK/LLM.

**Tests:**

* `tests/unit/tools/test_summarization.py` – 18 tests (prompt composition, truncation, JSON parsing variants, error paths).
* `tests/agents/test_summarizer_agent.py` – 11 tests (single/multiple contents, empty inputs, dict vs model, error handling, metadata preservation).

---

### Phase 5 – RAG Ingestion Layer ✅

**File:** `tools/rag_ingest.py`

* `class RagIngestClient(Protocol)`

  ```python
  async def ingest_summary(self, summary: BlogSummary) -> None
  ```

* `class HttpRagIngestClient(RagIngestClient)`

  * `__init__(base_url, uuid, api_key=None, timeout=10.0)`

    * Normalizes `base_url` (no trailing slash).
    * Stores `uuid` as corpus ID.
    * Optional `api_key` → `Authorization: Bearer ...`.
  * `async ingest_summary(summary: BlogSummary) -> None`

    * Uses `summary.to_rag_document()` as `"document"`.

    * `_build_payload(summary, uuid)` → JSON:

      ```json
      {
        "document": "<doc>",
        "doc_index": 0,
        "doc_metadata": {
          "blog_id": "...",
          "title": "...",
          "url": "...",
          "published_at": "...",
          "keywords": ["..."],
          "source": "nvidia_tech_blog",
          "uuid": "<corpus uuid>"
        },
        "uuid": "<corpus uuid>"
      }
      ```

    * POST to `{base_url}/add_doc` via `httpx.AsyncClient`.

    * Raises `httpx.HTTPStatusError` on non-2xx.

**Tests:** `tests/unit/tools/test_rag_ingest_payloads.py` – 12 tests (payload structure, base_url normalization, auth header, non-2xx handling, success cases, timeout config, context manager support).

---

### Phase 6 – RAG Retrieval + QA Agent ✅

**File:** `tools/rag_retrieve.py`

* `class RagRetrieveClient(Protocol)`

  ```python
  async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]
  ```

* `class HttpRagRetrieveClient(RagRetrieveClient)`

  * `__init__(base_url, uuid, api_key=None, timeout=10.0)`

    * Normalizes base_url.
  * `async retrieve(query, k=5) -> List[RetrievedDoc]`

    * `_build_query_payload(query, uuid, k)` → JSON:

      ```json
      {
        "question": "<query>",
        "uuid": "<corpus uuid>",
        "top_k": 5
      }
      ```

    * POST to `{base_url}/query`.

    * Maps response:

      ```json
      {
        "results": [
          {
            "page_content": "...",
            "score": 0.87,
            "metadata": {
              "blog_id": "...",
              "title": "...",
              "url": "...",
              ...
            }
          }
        ]
      }
      ```

    * `_map_result_item(item)`:

      * Returns a `RetrievedDoc` or `None` for malformed items.
      * Clamps `score` to [0, 1].
      * Skips malformed entries silently.

    * Raises on non-2xx via `raise_for_status()`.

**File:** `agents/qa_agent.py`

* `class QaModelLike(Protocol)`

  ```python
  def generate_answer(self, question: str, docs: list[RetrievedDoc]) -> str
  ```

* `class QAAgent`

  ```python
  class QAAgent:
      def __init__(self, rag_client: RagRetrieveClient, model: QaModelLike): ...
      async def answer(self, question: str, k: int = 5) -> tuple[str, list[RetrievedDoc]]:
          ...
  ```

Behavior:

* Calls `rag_client.retrieve(question, k)` → docs.
* If docs empty:

  * Returns conservative answer ("couldn't find any relevant NVIDIA blog posts…") + `[]`.
* Else:

  * Calls `model.generate_answer(question, docs)` and returns `(answer_text, docs)`.

**Tests:**

* `tests/unit/tools/test_rag_retrieval_payloads.py` – 15 tests:

  * Payload/URL structure, auth header, mapping results, malformed entries, non-2xx, base_url normalization, empty results, custom `k`.

* `tests/agents/test_qa_agent.py` – 6 tests:

  * Normal retrieval case, no-docs case, custom `k`, single-doc case, docs passed correctly to model, multiple queries.

---

## 4. Testing & Quality Summary

| Area                | Test File                        | Count   | Status |
| ------------------- | -------------------------------- | ------- | ------ |
| Contracts           | `test_contracts.py`              | 22      | ✅      |
| Discovery tools     | `test_discovery_tool.py`         | 20      | ✅      |
| Scraper tools       | `test_scraper_parser.py`         | 14      | ✅      |
| Summarization tools | `test_summarization.py`          | 18      | ✅      |
| Summarizer agent    | `test_summarizer_agent.py`       | 11      | ✅      |
| RAG ingest tools    | `test_rag_ingest_payloads.py`    | 12      | ✅      |
| RAG retrieve tools  | `test_rag_retrieval_payloads.py` | 15      | ✅      |
| QA agent            | `test_qa_agent.py`               | 6       | ✅      |
| **TOTAL**           |                                  | **118** | ✅      |

All tests are:

* Pure Python / async, **no real network**.
* Built on mocks/stubs (`httpx.MockTransport`, Stub clients, Stub models).
* Deterministic and fast.

---

## 5. Assumptions, Design Choices & Gaps

### Assumptions

* NVIDIA tech blogs follow HTML patterns that our discovery/scraper can handle (posts/articles, time tags, headings).
* RAG backend exposes:

  * `/add_doc` for ingestion.
  * `/query` for retrieval with `{question, uuid, top_k}`.
* Scores returned ~[0,1]; we clamp anyway.
* Summaries + retrieved docs are *sufficient context* for QA answers.

### Design Choices

* **Protocol-based abstraction** for all external integration:

  * `HtmlFetcher`, `RagIngestClient`, `RagRetrieveClient`, `QaModelLike`.
* **LLM-agnostic utilities**:

  * Summarization prompt + parsing separated from agent wiring.
* **No ADK coupling in tools**:

  * Tools are pure; agents handle ADK/LLM concerns.
* **Graceful degradation**:

  * Skip malformed entries in discovery and retrieval rather than throwing.

### Remaining Gaps (Future Phases)

* No ADK `SequentialAgent/ParallelAgent` workflow yet (Phase 7).
* No session/memory/compaction wiring (Phase 8).
* No eval harness / LLM-as-judge / e2e tests (Phase 9).
* No explicit use of MCP tools (`context7`, `cloud-run`, `storage`) yet:

  * `HtmlFetcher` could be backed by a Cloud Run / MCP scraper.
  * RAG endpoints likely hosted on Cloud Run.
  * GCS used to archive raw HTML / summaries / logs.

---

## 6. Next Logical Phases

You're now perfectly positioned for:

1. **Phase 7 – Workflow Orchestration (ADK)**

   * Build WatcherAgent, ScraperAgent, Summarizer pipeline, Ingestor step.
   * Root `SequentialAgent` that runs:

     1. Discovery → `BlogPost` list
     2. Scraper → `RawBlogContent` list
     3. SummarizerAgent → `BlogSummary` list
     4. RAG Ingest → HTTP ingestion
   * Workflow tests in `tests/workflows/`.

2. **Phase 8 – Context, Session, Memory & Compaction**

   * Wire ADK `SessionService`, state prefixes (`app:`, `user:`, `temp:`).
   * Define how we store:

     * `app:last_seen_blog_id`
     * `state["blogs"]`, `state["raw_contents"]`, `state["summaries"]`
   * Add compaction for long-running sessions.

3. **Phase 9 – Evaluation & E2E**

   * Golden query set over a controlled mini-corpus.
   * QA evaluation harness.
   * E2E smoke test from "fake feed HTML" → "user asks a question".

When you're ready, I can now draft the **Phase 7 prompt** for Cursor, tailored exactly to this current state.
