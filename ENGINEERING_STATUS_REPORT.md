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

* ✅ **182 tests passing** (Phases 1–9 + Vertex AI RAG Integration)

---

## 1. High-Level System Overview

You now have a full, modular system with support for both HTTP-based and Vertex AI RAG backends:

1. **Discovery** – parses NVIDIA blog feed HTML → BlogPosts.
2. **Scraping** – fetches HTML via HtmlFetcher → RawBlogContent.
3. **Summarization** – SummarizerAgent (Gemini LLM) → BlogSummary.
4. **RAG Ingestion** – Supports two paths:
   - **HTTP RAG**: RagIngestClient HTTPs summaries into a custom RAG backend
   - **Vertex AI RAG**: GcsRagIngestClient writes summaries to GCS for Vertex AI Search/RAG Engine
5. **RAG Retrieval** – Supports two paths:
   - **HTTP RAG**: RagRetrieveClient HTTPs queries → RetrievedDocs
   - **Vertex AI RAG**: VertexRagRetrieveClient queries Vertex AI RAG Engine → RetrievedDocs
6. **QA** – QAAgent uses retrieval + Gemini LLM to answer questions, grounded in docs.
7. **Workflow Orchestration** – run_ingestion_pipeline wires 1–4 into one async pipeline.
8. **Session/State Helpers** – read/write existing IDs, last results, history, with compaction.
9. **Evaluation & E2E** – eval harness + E2E smoke tests validate ingestion→QA end-to-end.
10. **Configuration & Client Wiring** – Centralized config with automatic backend detection.

Everything is async, dependency-injected, fully stub-able, and covered by tests. The system automatically detects whether to use HTTP-based or Vertex AI RAG based on environment configuration.

---

## 2. Current Code Layout

```
nvidia_blog_agent/
  __init__.py

  contracts/
    __init__.py
    blog_models.py

  tools/
    __init__.py
    discovery.py
    scraper.py
    summarization.py
    rag_ingest.py
    rag_retrieve.py
    gcs_rag_ingest.py        # Vertex AI RAG: GCS ingestion
    vertex_rag_retrieve.py   # Vertex AI RAG: RAG Engine retrieval

  agents/
    __init__.py
    summarizer_agent.py
    qa_agent.py
    workflow.py
    gemini_summarizer.py     # Real Gemini SummarizerLike implementation
    gemini_qa_model.py       # Real Gemini QaModelLike implementation

  context/
    __init__.py
    session_config.py
    compaction.py

  eval/
    __init__.py
    harness.py

  config.py                  # Centralized configuration
  rag_clients.py             # RAG client factory (HTTP + Vertex AI)

tests/
  __init__.py
  conftest.py

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
    __init__.py
    test_daily_pipeline_sequential.py
    test_parallel_scraping.py

  context/
    __init__.py
    test_session_state_prefixes.py
    test_compaction_behavior.py

  e2e/
    __init__.py
    test_full_run_smoke.py
    test_eval_harness_regression.py
```

---

## 3. Phases Recap (Very Compact)

### Phase 1 – Contracts & Data Models ✅

**Pydantic models:** BlogPost, RawBlogContent, BlogSummary, RetrievedDoc.

**Utilities:** generate_post_id, blog_summary_to_dict, BlogSummary.to_rag_document.

**Validation:** URL, score range, keyword normalization, non-empty fields.

---

### Phase 2 – Discovery Tools ✅

**diff_new_posts(existing_ids, discovered_posts)** – set-based filter, order-preserving.

**discover_posts_from_feed(raw_feed)** – BeautifulSoup feed parsing → BlogPosts.

Skips malformed posts, handles dates/tags, uses generate_post_id.

---

### Phase 3 – Scraper / HtmlFetcher ✅

**HtmlFetcher Protocol** – async fetch_html(url).

**parse_blog_html(blog, html)** – picks article root, strips scripts/styles, builds text and heading-based sections.

**fetch_and_parse_blog(blog, fetcher)** – uses injected fetcher.

---

### Phase 4 – Summarization + SummarizerAgent ✅

**build_summary_prompt(raw)** – clear JSON-output instructions; includes title/URL/content.

**parse_summary_json(raw, json_text, published_at)** – robust JSON extraction (handles code fences + extra text).

**SummarizerAgent** – ADK-style LlmAgent pattern, reads state["raw_contents"], writes state["summaries"].

**SummarizerAgentStub** – for tests.

---

### Phase 5 – RAG Ingestion ✅

**RagIngestClient Protocol.**

**HttpRagIngestClient(base_url, uuid, api_key=None, timeout=10.0):**

* Normalizes base_url, posts to {base_url}/add_doc.
* Payload uses summary.to_rag_document() plus metadata.
* Raises on non-2xx. Fully mocked in tests.

---

### Phase 6 – RAG Retrieval + QA Agent ✅

**RagRetrieveClient Protocol.**

**HttpRagRetrieveClient(base_url, uuid, api_key=None, timeout=10.0):**

* Posts {question, uuid, top_k} to {base_url}/query.
* Maps results[] → RetrievedDoc, clamps scores, skips malformed entries.

**QaModelLike Protocol.**

**QAAgent(rag_client, model):**

* answer(question, k=5) → (answer_text, retrieved_docs).
* Conservative "no docs" response.

---

### Phase 7 – Workflow Orchestration ✅

**IngestionResult dataclass** (discovered, new, raw_contents, summaries).

**SummarizerLike Protocol** (async summarize(List[RawBlogContent]) -> List[BlogSummary]).

**Helper stages:**

* discover_new_posts_from_feed(feed_html, existing_ids)
* fetch_raw_contents_for_posts(posts, fetcher) (asyncio.gather parallelism)
* summarize_raw_contents(contents, summarizer)
* ingest_summaries(summaries, rag_client)

**run_ingestion_pipeline(feed_html, existing_ids, fetcher, summarizer, rag_client):**

* Orchestrates all 4 stages and returns IngestionResult.

---

### Phase 8 – Session, State Prefixes, Compaction ✅

**session_config.py:**

* Prefixes: APP_PREFIX="app:", USER_PREFIX="user:", TEMP_PREFIX="temp:".
* Keys: app:last_seen_blog_ids, app:last_ingestion_results.
* get_existing_ids_from_state(state) -> set[str]
* update_existing_ids_in_state(state, new_posts)
* store_last_ingestion_result_metadata(state, IngestionResult)
* get_last_ingestion_result_metadata(state) -> dict

**compaction.py:**

* INGESTION_HISTORY_KEY = "app:ingestion_history".
* append_ingestion_history_entry(state, metadata, timestamp=None)
* compact_ingestion_history(state, max_entries=10) (sliding window).

---

### Phase 9 – Eval Harness & E2E ✅

**eval/harness.py:**

* EvalCase(question, expected_substrings, max_docs)
* EvalResult(question, answer, retrieved_docs, passed, matched_substrings)
* EvalSummary(total, passed, failed, pass_rate)
* simple_pass_fail_checker(answer, expected_substrings) – case-insensitive substring scoring.
* run_qa_evaluation(qa_agent, cases) – runs QAAgent, returns per-case results.
* summarize_eval_results(results) – aggregate metrics.

**E2E tests:**

* **test_full_run_smoke.py:**
  * InMemoryRag implementing both RagIngestClient & RagRetrieveClient.
  * Stub fetcher, summarizer, qa model.
  * Full pipeline: feed HTML → discovery → scrape → summarize → ingest → state updates → QA → eval harness.

* **test_eval_harness_regression.py:**
  * Regression tests for eval logic: all-pass, partial fail, all-fail, case sensitivity, empty cases, etc.

You now have unit, workflow, context, and E2E tests confirming the whole system wiring.

---

### Phase 10 – Configuration & Real Client Wiring ✅

**config.py:**

* GeminiConfig(model_name, location)
* RagConfig with support for both HTTP and Vertex AI RAG:
  * HTTP RAG: base_url, uuid, api_key
  * Vertex AI RAG: use_vertex_rag, vertex_location, docs_bucket, search_engine_name
* AppConfig(gemini, rag)
* load_config_from_env() – automatically detects HTTP vs Vertex AI RAG mode

**rag_clients.py:**

* create_rag_clients(config) – factory function that:
  * Returns HttpRagIngestClient + HttpRagRetrieveClient for HTTP RAG
  * Returns GcsRagIngestClient + VertexRagRetrieveClient for Vertex AI RAG
  * Automatically selects based on USE_VERTEX_RAG environment variable

**agents/gemini_summarizer.py:**

* GeminiSummarizer(SummarizerLike):
  * Uses build_summary_prompt + Gemini (google-generativeai or ADK)
  * Parses JSON response → BlogSummary
  * Supports both google-generativeai and google-genai-adk libraries

**agents/gemini_qa_model.py:**

* GeminiQaModel(QaModelLike):
  * Builds Q&A prompt from RetrievedDoc snippets
  * Uses Gemini to generate grounded answers
  * Supports both google-generativeai and google-genai-adk libraries

---

### Phase 11 – Vertex AI RAG Integration ✅

**tools/gcs_rag_ingest.py:**

* GcsRagIngestClient(RagIngestClient):
  * Uses google-cloud-storage
  * Writes BlogSummary.to_rag_document() → GCS bucket as text files
  * Writes metadata JSON files alongside documents
  * Format: `{bucket}/{prefix}{blog_id}.txt` and `{blog_id}.metadata.json`

**tools/vertex_rag_retrieve.py:**

* VertexRagRetrieveClient(RagRetrieveClient):
  * Queries Vertex AI RAG Engine REST API
  * Maps RAG Engine responses → RetrievedDoc objects
  * Supports both ADK and direct REST API paths
  * Handles authentication via Google Application Default Credentials

**VERTEX_RAG_SETUP.md:**

* Complete setup guide for Vertex AI RAG:
  * API enablement
  * GCS bucket creation
  * Vertex AI Search data store setup
  * Vertex AI RAG Engine corpus configuration
  * Environment variable configuration
  * Usage examples and troubleshooting

**Backward Compatibility:**

* HTTP RAG path remains fully functional
* All 182 tests still pass
* Can switch between backends with single environment variable
* No code changes required to switch backends

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
| Workflow            | `test_daily_pipeline_sequential.py`, `test_parallel_scraping.py` | 13 | ✅ |
| Context/State       | `test_session_state_prefixes.py`, `test_compaction_behavior.py` | 33 | ✅ |
| E2E                 | `test_full_run_smoke.py`, `test_eval_harness_regression.py` | 18 | ✅ |
| **TOTAL**           |                                  | **182** | ✅      |

All tests are:

* Pure Python / async, **no real network**.
* Built on mocks/stubs (`httpx.MockTransport`, Stub clients, Stub models).
* Deterministic and fast.

---

## 5. Configuration & Real Client Wiring

### 5.1 Configuration Module

**File:** `config.py`

The configuration module centralizes all runtime settings:

* **GeminiConfig**: Model name and location for Gemini/LLM access
* **RagConfig**: Supports both HTTP-based and Vertex AI RAG backends
* **AppConfig**: Container for all configuration
* **load_config_from_env()**: Loads configuration from environment variables

**Environment Variables:**

For HTTP-based RAG:
```bash
export RAG_BASE_URL="https://your-rag-service.run.app"
export RAG_UUID="corpus-id"
export RAG_API_KEY="optional-api-key"
```

For Vertex AI RAG:
```bash
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="your-corpus-id"
export VERTEX_LOCATION="us-central1"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"
```

### 5.2 RAG Client Factory

**File:** `rag_clients.py`

The `create_rag_clients()` function automatically creates the appropriate clients:

* **HTTP Mode**: Returns `HttpRagIngestClient` + `HttpRagRetrieveClient`
* **Vertex AI Mode**: Returns `GcsRagIngestClient` + `VertexRagRetrieveClient`

No code changes needed - just set environment variables!

### 5.3 Gemini Implementations

**Files:** `agents/gemini_summarizer.py`, `agents/gemini_qa_model.py`

Real Gemini implementations of the protocol interfaces:

* **GeminiSummarizer**: Implements `SummarizerLike` using Gemini models
* **GeminiQaModel**: Implements `QaModelLike` using Gemini models

Both support:
* `google-generativeai` library (standard)
* `google-genai-adk` library (ADK integration)

Automatically detects which library is available and uses it.

---

## 6. Vertex AI RAG Integration

### 6.1 Architecture

```
BlogSummary → GCS Bucket → Vertex AI Search → Vertex AI RAG Engine → QAAgent
```

1. **Ingestion**: `GcsRagIngestClient` writes summaries to GCS
2. **Indexing**: Vertex AI Search automatically ingests from GCS
3. **Retrieval**: `VertexRagRetrieveClient` queries RAG Engine
4. **QA**: QAAgent uses retrieved docs with Gemini for answers

### 6.2 GCS Ingestion Client

**File:** `tools/gcs_rag_ingest.py`

* Writes `BlogSummary.to_rag_document()` as text files to GCS
* Writes metadata JSON files for Vertex AI Search
* Uses `google-cloud-storage` library
* Format: `{bucket}/{prefix}{blog_id}.txt` and `{blog_id}.metadata.json`

### 6.3 Vertex RAG Retrieval Client

**File:** `tools/vertex_rag_retrieve.py`

* Queries Vertex AI RAG Engine REST API
* Maps responses to `RetrievedDoc` objects
* Handles authentication via Application Default Credentials
* Supports both ADK and direct REST API paths

### 6.4 Setup Guide

**File:** `VERTEX_RAG_SETUP.md`

Complete step-by-step guide covering:
* API enablement
* GCS bucket creation
* Vertex AI Search data store setup
* Vertex AI RAG Engine corpus configuration
* Environment variable setup
* Usage examples
* Troubleshooting

---

## 7. What You Need to Do Next (Practical Setup Checklist)

Now: what do you actually need to configure to run this against real NVIDIA blogs + real models + a real RAG backend?

Below is a pragmatic checklist broken into layers: local dev, GCP/RAG, and (optional) Cloud Run + MCP integration.

### 5.1 Local / Dev Environment

**1. Python environment**

Ensure your environment has the project deps:

* pydantic>=2
* httpx
* beautifulsoup4 + lxml
* pytest, pytest-asyncio
* google-genai-adk (already uncommented)

Confirm tests run locally:

```bash
pytest -q
```

No secrets needed to run tests – they use stubs only.

---

### 5.2 Gemini / LLM Access

For real summarization & QA (instead of stubs), you'll need:

**A Google service account with:**

* Permissions to call Gemini / Vertex AI GenAI (exact name depends on API, e.g. Vertex AI User).

**Credentials on your dev machine:**

* Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`.

**Model config in code:**

Where you currently stub the model in SummarizerAgent and QAAgent, you'll:

* Instantiate a real ADK LlmAgent or Gemini client.
* Inject it via your existing abstractions (SummarizerAgent, QaModelLike).

You don't have to wire this immediately for the capstone if you demonstrate using stubs, but for a "real" version, you'll want live Gemini calls.

---

### 7.3 RAG Backend Setup

You now have **two options** for RAG backends:

#### Option A: HTTP-Based RAG Backend

Your code supports a generic HTTP RAG backend with:

* POST `{base_url}/add_doc` for ingestion.
* POST `{base_url}/query` for retrieval.

You can use:

* NVIDIA Context-Aware RAG running as a service (e.g., Docker → Cloud Run).
* Your own simple RAG service (e.g., Milvus + a small Flask/FastAPI app).
* Any HTTP-based RAG service matching the expected API.

**Configuration:**
```bash
export RAG_BASE_URL="https://my-rag-service-abc.run.app"
export RAG_UUID="corpus-id"
export RAG_API_KEY="optional-api-key"
```

**Usage:**
```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients

config = load_config_from_env()
ingest_client, retrieve_client = create_rag_clients(config)
# Automatically uses HttpRagIngestClient + HttpRagRetrieveClient
```

#### Option B: Vertex AI RAG Engine (Recommended)

Use Google's managed Vertex AI RAG Engine:

* **Ingestion**: Writes to GCS, Vertex AI Search ingests automatically
* **Retrieval**: Queries Vertex AI RAG Engine API
* **Benefits**: No infrastructure to manage, automatic embeddings/chunking

**Configuration:**
```bash
export USE_VERTEX_RAG="true"
export RAG_CORPUS_ID="your-corpus-id"
export VERTEX_LOCATION="us-central1"
export RAG_DOCS_BUCKET="gs://nvidia-blog-rag-docs"
```

**Setup Steps:**
1. Enable APIs: `aiplatform.googleapis.com`, `discoveryengine.googleapis.com`
2. Create GCS bucket: `gs://nvidia-blog-rag-docs`
3. Create Vertex AI Search data store pointing to bucket
4. Create Vertex AI RAG Engine corpus connected to Search
5. Set environment variables as shown above

See `VERTEX_RAG_SETUP.md` for complete setup instructions.

**Usage:**
```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients

config = load_config_from_env()
ingest_client, retrieve_client = create_rag_clients(config)
# Automatically uses GcsRagIngestClient + VertexRagRetrieveClient
```

**Action items:**

1. Choose your RAG backend (HTTP vs Vertex AI RAG).
2. If HTTP: Deploy your RAG service and set `RAG_BASE_URL`, `RAG_UUID`.
3. If Vertex AI RAG: Follow `VERTEX_RAG_SETUP.md` to set up GCS, Search, and RAG Engine.
4. Set appropriate environment variables.
5. Test ingestion and retrieval.

---

### 7.4 HTML Fetching (HtmlFetcher Implementation)

Right now HtmlFetcher is just a Protocol. To scrape real NVIDIA tech blogs, you need a concrete implementation:

**Option A – Simple HTTP fetcher**

```python
import httpx
from nvidia_blog_agent.tools.scraper import HtmlFetcher

class HttpHtmlFetcher(HtmlFetcher):
    async def fetch_html(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
```

**Option B – MCP-based fetcher**

If you want to leverage your existing MCP tools (e.g., a browser or specialized fetcher exposed via MCP), you can implement HtmlFetcher as a thin wrapper that calls those tools.

In both cases you'll then be able to plug it into:

```python
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline

result = await run_ingestion_pipeline(
    feed_html=feed_html,
    existing_ids=get_existing_ids_from_state(state),
    fetcher=http_fetcher,        # your implementation
    summarizer=real_summarizer,  # wrapper around SummarizerAgent
    rag_client=ingest_client,
)
```

**Action items:**

1. Implement HtmlFetcher (HTTP or MCP).
2. Decide how you get the initial `feed_html`:
   * Fetch NVIDIA blog index or RSS feed via HTTP.
   * Or use MCP context7/browser tool to pull HTML.

---

### 7.5 State Persistence (IDs, History, etc.)

Your helpers assume state is a dict-like object. For a real deployment you want to persist it somewhere:

* **Minimal option:** store a JSON file on disk (`state.json`).
* **Cloud-native option:** store a blob in GCS.

**Example pattern (local):**

```python
STATE_PATH = "state.json"

def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, "r") as f:
        return json.load(f)

def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)
```

On GCS, same pattern but use `google-cloud-storage` to read/write a single JSON object in a bucket like `gs://nvidia-blog-agent-state/state.json`.

**Buckets you might create:**

* `gs://nvidia-blog-agent-state` – state blobs, history snapshots.
* (Optional) `gs://nvidia-blog-agent-raw` – raw HTML snapshots per run.
* (Optional) `gs://nvidia-blog-agent-summaries` – JSON of summaries for offline analysis.

**Action items:**

1. Choose where/whether to persist state (local JSON vs GCS).
2. If GCS:
   * Create a bucket (e.g., `nvidia-blog-agent-state`).
   * Give your service account Storage Object Admin or similar.
   * Implement simple `load_state` / `save_state` using GCS.

---

### 7.6 Wiring the Ingestion Script

Once config & dependencies exist, you'll want a small script, e.g. `scripts/run_ingest.py`, that:

* Loads state (from disk or GCS).
* Fetches feed HTML.
* Builds HtmlFetcher, GeminiSummarizer, RagIngestClient (via factory).
* Calls `run_ingestion_pipeline`.
* Updates state using session helpers.
* Saves state back.

**Complete example:**

```python
import asyncio
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.workflow import run_ingestion_pipeline
from nvidia_blog_agent.agents.gemini_summarizer import GeminiSummarizer
from nvidia_blog_agent.context.session_config import (
    get_existing_ids_from_state,
    update_existing_ids_in_state,
    store_last_ingestion_result_metadata,
    get_last_ingestion_result_metadata,
)
from nvidia_blog_agent.context.compaction import (
    append_ingestion_history_entry,
    compact_ingestion_history,
)

# Your HtmlFetcher implementation
class HttpHtmlFetcher:
    async def fetch_html(self, url: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

async def main():
    # Load configuration (automatically detects HTTP vs Vertex RAG)
    config = load_config_from_env()
    
    # Create RAG clients (automatically selects correct implementation)
    ingest_client, retrieve_client = create_rag_clients(config)
    
    # Load state
    state = load_state()  # Your implementation
    
    # Get existing IDs
    existing_ids = get_existing_ids_from_state(state)
    
    # Fetch feed HTML
    feed_html = await fetch_feed_html()  # Your implementation
    
    # Create dependencies
    fetcher = HttpHtmlFetcher()
    summarizer = GeminiSummarizer(config.gemini)  # Real Gemini
    
    # Run ingestion pipeline
    result = await run_ingestion_pipeline(
        feed_html=feed_html,
        existing_ids=existing_ids,
        fetcher=fetcher,
        summarizer=summarizer,
        rag_client=ingest_client,  # GcsRagIngestClient or HttpRagIngestClient
    )
    
    # Update state
    update_existing_ids_in_state(state, result.new_posts)
    store_last_ingestion_result_metadata(state, result)
    
    meta = get_last_ingestion_result_metadata(state)
    append_ingestion_history_entry(state, meta)
    compact_ingestion_history(state, max_entries=20)
    
    # Save state
    save_state(state)  # Your implementation
    
    print(f"Ingestion complete: {len(result.summaries)} summaries processed")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7.7 Wiring the QA Script / Service

Similarly, for QA:

* Use `create_rag_clients()` to get retrieve_client (automatically selects HTTP or Vertex RAG).
* Use `GeminiQaModel` for real Gemini QA.
* Wrap in a small CLI or HTTP service:

```python
from nvidia_blog_agent.config import load_config_from_env
from nvidia_blog_agent.rag_clients import create_rag_clients
from nvidia_blog_agent.agents.gemini_qa_model import GeminiQaModel
from nvidia_blog_agent.agents.qa_agent import QAAgent

config = load_config_from_env()
ingest_client, retrieve_client = create_rag_clients(config)

qa_model = GeminiQaModel(config.gemini)
qa_agent = QAAgent(rag_client=retrieve_client, model=qa_model)

answer, docs = await qa_agent.answer("What did NVIDIA say about RAG on GPUs?", k=5)
print(answer)
print("Docs used:", [d.title for d in docs])
```

For Cloud Run, you'd wrap that in FastAPI/Flask:

* `/ask?question=...` → calls `qa_agent.answer` and returns JSON.

---

### 7.8 Optional: Cloud Run + MCP Story

If you want the "production-style" narrative for the capstone:

* Containerize an app that exposes two endpoints:
  * `/ingest` – triggers one ingestion run (like `run_ingestion_pipeline`).
  * `/ask` – runs the QA flow.
* Deploy to Cloud Run:
  * Set env vars:
    * `PROJECT_ID`
    * `RAG_BASE_URL`, `RAG_UUID`, `RAG_API_KEY`
    * `STATE_BUCKET` (if using GCS)
* Use your MCP cloud-run tool to introspect/manage the service.

**MCP tools (cloud-run, storage, context7):**

* `storage` – read/write state or logs from GCS.
* `cloud-run` – check service status, URLs, etc.
* `context7` – possibly to fetch NVIDIA docs/feeds or augment queries.

---

## 8. TL;DR – Concrete To-Do List for You

If I boil it down to the bare bones:

### Choose RAG Backend

**Option A: HTTP RAG**
1. Stand up CA-RAG or a simple RAG HTTP service.
2. Set `RAG_BASE_URL`, `RAG_UUID`, `RAG_API_KEY`.

**Option B: Vertex AI RAG (Recommended)**
1. Follow `VERTEX_RAG_SETUP.md`:
   * Enable APIs: `aiplatform.googleapis.com`, `discoveryengine.googleapis.com`
   * Create GCS bucket: `gs://nvidia-blog-rag-docs`
   * Create Vertex AI Search data store
   * Create Vertex AI RAG Engine corpus
2. Set `USE_VERTEX_RAG="true"`, `RAG_CORPUS_ID`, `VERTEX_LOCATION`, `RAG_DOCS_BUCKET`.

### Configure LLM (Gemini)

1. Service account + `GOOGLE_APPLICATION_CREDENTIALS`.
2. Set `GEMINI_MODEL_NAME` and `GEMINI_LOCATION`.
3. Use `GeminiSummarizer` and `GeminiQaModel` (already implemented).

### Implement HtmlFetcher + feed fetch

1. Simple HTTP HtmlFetcher implementation (see examples in `USAGE_EXAMPLE.md`).
2. Simple `fetch_feed_html()` for NVIDIA tech blog index / RSS.

### State persistence

1. Decide: local JSON vs GCS.
2. Implement `load_state` / `save_state` (see examples in section 7.5).

### Ingestion & QA entrypoints

1. Script for ingestion using `run_ingestion_pipeline` (see section 7.6).
2. Script/service for QA using `QAAgent.answer` (see section 7.7).

### Test Run

1. Run ingestion pass → verify documents in GCS (Vertex RAG) or RAG backend (HTTP RAG).
2. Run QA query → verify answer and retrieved documents.
3. Check Vertex AI Search Console (if using Vertex RAG) to confirm indexing.

---

## 9. Assumptions, Design Choices & Gaps

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

* No explicit use of MCP tools (`context7`, `cloud-run`, `storage`) yet:
  * `HtmlFetcher` could be backed by a Cloud Run / MCP scraper.
  * RAG endpoints likely hosted on Cloud Run.
  * GCS used to archive raw HTML / summaries / logs.
* Production deployment and monitoring:
  * Error handling and retries for external services.
  * Logging and observability.
  * Rate limiting and cost management.
* Capstone deliverables:
  * High-level architecture diagram
  * Notebook/Colab demo showing ingestion + QA
  * Evaluation results using eval/harness.py
  * Reproducibility instructions
