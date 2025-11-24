# Engineering Status Report

This document provides technical details about the NVIDIA Tech Blog Agent system architecture, configuration, and runtime behavior.

## Vertex RAG Runtime Config

### Backend Architecture

The system uses **Vertex AI RAG Engine + Vertex AI Search + GCS** as the primary RAG backend:

- **RAG Engine**: Vertex AI RAG Engine manages retrieval and grounding
- **Search Backend**: Vertex AI Search provides the corpus and indexing
- **Storage**: Google Cloud Storage (GCS) bucket for document storage
- **Docs Bucket**: `gs://nvidia-blog-rag-docs` (configurable via `RAG_DOCS_BUCKET`)

### Embedding Model

- **Model**: `text-embedding-005` (default and recommended)
- **Publisher**: `publishers/google/models/text-embedding-005`
- **Dimension**: Full/default embedding dimension (high quality)
- **Usage**: Automatically used by Vertex AI RAG Engine when corpus is created with Vertex AI Search backend

### Retrieval Configuration

- **Hybrid Search**: **ON** (enabled by default in Vertex AI Search)
  - Combines vector similarity search with keyword/BM25 search
  - Provides better retrieval performance than vector-only search
- **Reranking**: **ON** (available via Vertex AI ranking API)
  - Uses semantic reranking for improved relevance
  - Can be configured in retrieval requests
- **Chunking**:
  - `chunk_size`: 1024 tokens
  - `chunk_overlap`: 256 tokens
  - Configured in Vertex AI Search data store settings

### Retrieval Parameters

- **Initial Retrieval**: `top_k=8-10` documents retrieved from RAG Engine (recommended range)
  - The `k` parameter is configurable; 8-10 is the recommended range for optimal performance
- **QA Input**: Top 4-6 documents (after reranking) passed to Gemini for answer generation (recommended range)
  - The actual number of documents used depends on the `k` parameter passed to the QA agent
- **QA LLM**: Gemini 1.5 Pro
- **QA Temperature**: Uses default Gemini temperature behavior (typically ~0.2 for factual responses)
  - Note: Temperature is not explicitly set in code; Gemini uses its default behavior optimized for factual responses

### Environment Variables

#### Required for Vertex AI RAG

- `USE_VERTEX_RAG`: Set to `"true"` to enable Vertex AI RAG Engine
- `RAG_CORPUS_ID`: Vertex AI RAG corpus ID (numeric ID from corpus resource name)
- `RAG_DOCS_BUCKET`: GCS bucket for documents (e.g., `gs://nvidia-blog-rag-docs`)
- `VERTEX_LOCATION`: Region for Vertex AI services (e.g., `us-central1`)

#### Optional

- `RAG_SEARCH_ENGINE_NAME`: Vertex AI Search serving config resource name (if querying Search directly)
- `GOOGLE_CLOUD_PROJECT`: GCP project ID (can also use `GCP_PROJECT`)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON file

#### State Persistence

- `STATE_PATH`: Path for state persistence
  - **Development**: `state.json` (local file)
  - **Production**: `gs://nvidia-blog-agent-state/state.json` (GCS bucket, recommended)

### Document Strategy

- **One document per blog post**: Each NVIDIA tech blog post becomes one Vertex RAG document
- **Content**: Full cleaned text from `RawBlogContent.text` (via `BlogSummary.to_rag_document()`)
- **Storage**: Documents written to GCS as `{blog_id}.txt` files
- **Metadata**: Stored as `{blog_id}.metadata.json` files in GCS
- **No separate storage**: Raw HTML and summaries are not stored in separate buckets beyond what GCS RAG ingest writes

### State Management

#### System/App State

State keys use `app:` prefix:
- `app:last_seen_blog_ids`: Set of previously seen blog post IDs
- `app:last_ingestion_results`: Results from the most recent ingestion run
- `app:ingestion_history`: Historical record of ingestion runs

State is persisted via `nvidia_blog_agent.context.state_persistence`:
- `load_state()`: Loads state from local JSON or GCS
- `save_state()`: Saves state to local JSON or GCS
- Supports both local files and GCS URIs (e.g., `gs://bucket/state.json`)

#### User State

- Reserved for future ADK/Vertex Agent integration
- Uses `user:` prefix
- Not required to be persisted in this phase

## System Architecture

### RAG Backend Selection

The system automatically detects which RAG backend to use:

1. **Vertex AI RAG** (Primary/Recommended):
   - Triggered when `USE_VERTEX_RAG=true`
   - Uses `GcsRagIngestClient` for ingestion
   - Uses `VertexRagRetrieveClient` for retrieval
   - Requires: `RAG_CORPUS_ID`, `VERTEX_LOCATION`, `RAG_DOCS_BUCKET`

2. **HTTP RAG** (Legacy/Alternative):
   - Triggered when `USE_VERTEX_RAG` is not set or `false`
   - Uses `HttpRagIngestClient` and `HttpRagRetrieveClient`
   - Requires: `RAG_BASE_URL`, `RAG_UUID`

### Pipeline Flow

1. **Discovery**: Parse NVIDIA blog feed HTML to find new posts
2. **Scraping**: Fetch and parse individual blog post content
3. **Summarization**: Generate summaries using Gemini 1.5 Pro
4. **Ingestion**: Write documents to RAG backend using `run_ingestion_pipeline()` (GCS for Vertex RAG)
5. **QA**: Retrieve relevant documents and generate grounded answers using Gemini 1.5 Pro

## Evaluation

The system includes an evaluation harness (`nvidia_blog_agent.eval.harness`) for testing QA performance:

- **EvalCase**: Defines test cases with questions and expected substrings
- **EvalResult**: Results from evaluating a single case
- **EvalSummary**: Summary statistics (pass rate, total cases, etc.)
- **run_qa_evaluation()**: Runs evaluation over multiple cases
- **summarize_eval_results()**: Computes summary statistics

See README.md for examples of running evaluations with Vertex RAG.

### Running Evaluations

Use the `scripts/run_eval_vertex.py` script to run evaluations against the Vertex AI RAG backend:

```bash
# Run with default test cases
python scripts/run_eval_vertex.py

# Run with verbose logging
python scripts/run_eval_vertex.py --verbose

# Save results to JSON file
python scripts/run_eval_vertex.py --output eval_results.json

# Use custom test cases from JSON file
python scripts/run_eval_vertex.py --cases-file my_cases.json
```

### Evaluation Results (Vertex RAG)

<!-- 
TODO: Fill in this section after running `python scripts/run_eval_vertex.py`
Copy the summary and key results from the output, or paste from the JSON output file.
-->

**Evaluation Date**: [YYYY-MM-DD]  
**Configuration**:
- RAG Backend: Vertex AI RAG Engine
- Corpus ID: `[corpus_id]`
- Location: `[vertex_location]`
- Embedding Model: `text-embedding-005`
- Gemini Model: `gemini-1.5-pro`
- Retrieval: `top_k=8-10` (recommended), reranking enabled

**Summary**:
- Total cases: [N]
- Passed: [N]
- Failed: [N]
- Pass rate: [X]%

**Key Findings**:
- [Add observations about retrieval quality, answer accuracy, etc.]

**Sample Results**:
1. **Question**: "[Example question]"
   - Status: ✅ PASS / ❌ FAIL
   - Retrieved docs: [N]
   - Top doc score: [X.XXXX]
   - Answer quality: [Brief assessment]

2. [Add more sample results...]

**Notes**:
- [Any observations about performance, edge cases, improvements needed, etc.]

## References

- [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md): Complete setup and deployment guide for Vertex AI RAG
- [README.md](README.md): User-facing documentation and usage examples
