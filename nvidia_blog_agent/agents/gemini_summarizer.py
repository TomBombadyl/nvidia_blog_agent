"""Gemini-based implementation of SummarizerLike protocol.

This module provides GeminiSummarizer, which uses Google's Gemini models
to summarize RawBlogContent objects into BlogSummary objects.
"""

import os
from typing import List
from nvidia_blog_agent.agents.workflow import SummarizerLike
from nvidia_blog_agent.contracts.blog_models import RawBlogContent, BlogSummary
from nvidia_blog_agent.tools.summarization import build_summary_prompt, parse_summary_json
from nvidia_blog_agent.config import GeminiConfig

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from google.genai.client import Client as GenaiClient
    from google.genai.types import GenerateContentConfig
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    GenaiClient = None
    GenerateContentConfig = None


class GeminiSummarizer(SummarizerLike):
    """Gemini-based implementation of SummarizerLike protocol.
    
    This summarizer uses Google's Gemini models to generate summaries from
    RawBlogContent objects. It can work with either the google-generativeai
    library or the ADK GenaiClient.
    
    Attributes:
        _cfg: Gemini configuration (model name, location).
        _client: Gemini client instance (genai.Client or GenaiClient).
        _use_adk: Whether to use ADK client (True) or genai library (False).
    """
    
    def __init__(self, gemini_cfg: GeminiConfig, client=None):
        """Initialize GeminiSummarizer.
        
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
                # Get project and location for Vertex AI
                project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
                location = gemini_cfg.location
                
                if project and location:
                    # Use Vertex AI (requires project and location)
                    self._client = GenaiClient(vertexai=True, project=project, location=location)
                else:
                    # Fall back to Google AI API (requires API key)
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
    
    async def summarize(self, contents: List[RawBlogContent]) -> List[BlogSummary]:
        """Summarize a batch of RawBlogContent objects into BlogSummary objects.
        
        For each RawBlogContent:
        1. Builds a prompt using build_summary_prompt()
        2. Calls Gemini model to generate JSON summary
        3. Parses JSON response into BlogSummary
        
        Args:
            contents: List of RawBlogContent objects to summarize.
        
        Returns:
            List of BlogSummary objects, one per input RawBlogContent.
        
        Raises:
            ValueError: If JSON parsing fails or required fields are missing.
            RuntimeError: If model call fails.
        """
        summaries: List[BlogSummary] = []
        
        for raw in contents:
            prompt = build_summary_prompt(raw)
            
            # Call Gemini model
            if self._use_adk:
                # Use ADK GenaiClient
                response = await self._client.aio.models.generate_content(
                    model=self._cfg.model_name,
                    contents=prompt,
                )
                json_text = response.text
            else:
                # Use google-generativeai library
                model = genai.GenerativeModel(self._cfg.model_name)
                response = await model.generate_content_async(prompt)
                json_text = response.text
            
            # Parse JSON response into BlogSummary
            summary = parse_summary_json(
                raw,
                json_text,
                published_at=raw.published_at if hasattr(raw, 'published_at') else None,
                categories=raw.categories
            )
            summaries.append(summary)
        
        return summaries

