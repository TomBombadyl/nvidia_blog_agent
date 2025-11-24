# NVIDIA Blog Agent

A modular, production-style NVIDIA Tech Blog Intelligence Agent using Google ADK, MCP, and a RAG backend (NVIDIA Context-Aware RAG or Vertex RAG).

## Description

This system:
1. Periodically discovers new NVIDIA technical blog posts
2. Fetches and parses the HTML content of those posts
3. Summarizes each post into structured summaries
4. Ingests those summaries into a RAG backend (CA-RAG or equivalent)
5. Exposes a user-facing QA agent that can answer questions about NVIDIA tech blogs, grounded in the RAG store

## Architecture

The project follows a clean, modular architecture with:
- **Contracts**: Core data models (Pydantic)
- **Tools**: Discovery, scraping, summarization, and RAG operations
- **Agents**: Workflow orchestration using Google ADK
- **Context**: Session management, memory, and compaction
- **Eval**: Evaluation harness for testing

## Getting Started

### Prerequisites

- Python 3.x
- Git

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/nvidia_blog_agent.git
cd nvidia_blog_agent
```

## Usage

Coming soon...

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license here]

## Contact

[Add your contact information here]

