"""Gemini-based implementation of QaModelLike protocol.

This module provides GeminiQaModel, which uses Google's Gemini models
to generate answers to questions based on retrieved documents.
"""

from nvidia_blog_agent.agents.qa_agent import QaModelLike
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.config import GeminiConfig

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from google.genai.client import Client as GenaiClient
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    GenaiClient = None


class GeminiQaModel(QaModelLike):
    """Gemini-based implementation of QaModelLike protocol.
    
    This QA model uses Google's Gemini models to generate answers to questions
    based on retrieved documents. It formats the documents as context and asks
    the model to answer strictly based on the provided snippets.
    
    Attributes:
        _cfg: Gemini configuration (model name, location).
        _client: Gemini client instance (genai.Client or GenaiClient).
        _use_adk: Whether to use ADK client (True) or genai library (False).
    """
    
    def __init__(self, gemini_cfg: GeminiConfig, client=None):
        """Initialize GeminiQaModel.
        
        Args:
            gemini_cfg: Gemini configuration (model name, location).
            client: Optional pre-configured client. If None, creates a new client.
                   Can be either genai.Client (ADK) or uses google.generativeai.
        
        Raises:
            ImportError: If neither google-generativeai nor ADK is available.
        """
        self._cfg = gemini_cfg
        self._use_adk = False
        
        if client is not None:
            self._client = client
            # Try to detect if it's an ADK client
            if ADK_AVAILABLE and isinstance(client, GenaiClient):
                self._use_adk = True
        else:
            # Create client based on what's available
            if ADK_AVAILABLE:
                self._client = GenaiClient()
                self._use_adk = True
            elif GENAI_AVAILABLE:
                genai.configure()  # Uses GOOGLE_APPLICATION_CREDENTIALS
                self._client = genai
            else:
                raise ImportError(
                    "Neither google-generativeai nor google-genai-adk is available. "
                    "Please install one of them: pip install google-generativeai or pip install google-genai-adk"
                )
    
    def generate_answer(self, question: str, docs: list[RetrievedDoc]) -> str:
        """Generate an answer to a question based on retrieved documents.
        
        This method:
        1. Formats retrieved documents as context blocks (title, URL, snippet)
        2. Builds a prompt instructing the model to answer based only on the provided snippets
        3. Calls Gemini model to generate the answer
        4. Returns the answer text
        
        Args:
            question: The user's question string.
            docs: List of RetrievedDoc objects to use as context for answering.
        
        Returns:
            Answer string generated based on the question and documents.
        
        Raises:
            RuntimeError: If model call fails.
        """
        if not docs:
            return "I couldn't find any relevant NVIDIA blog posts to answer this question."
        
        # Build context blocks from documents
        context_blocks = []
        for d in docs:
            context_blocks.append(
                f"Title: {d.title}\n"
                f"URL: {d.url}\n"
                f"Snippet: {d.snippet}"
            )
        context = "\n\n".join(context_blocks)
        
        # Build prompt
        prompt = (
            "You are an assistant answering questions strictly based on NVIDIA technical blog posts.\n"
            "Use ONLY the provided snippets. If the answer cannot be found in the snippets, "
            "say so clearly.\n\n"
            f"Question:\n{question}\n\n"
            f"Documents:\n{context}\n\n"
            "Answer:"
        )
        
        # Call Gemini model
        if self._use_adk:
            # Use ADK GenaiClient (synchronous call)
            # Note: ADK client has both sync and async methods
            # For sync protocol, we use the sync method
            response = self._client.models.generate_content(
                model=self._cfg.model_name,
                contents=prompt,
            )
            return response.text
        else:
            # Use google-generativeai library (synchronous)
            model = genai.GenerativeModel(self._cfg.model_name)
            response = model.generate_content(prompt)
            return response.text

