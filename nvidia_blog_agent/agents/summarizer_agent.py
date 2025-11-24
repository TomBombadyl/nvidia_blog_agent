"""SummarizerAgent for converting RawBlogContent to BlogSummary using LLM.

This module provides:
- SummarizerAgent: ADK LlmAgent that reads RawBlogContent from session.state,
  generates summaries using an LLM, and writes BlogSummary objects back.

The agent is designed to be testable using stub LLM implementations.
"""

from typing import Optional, List, Any
from datetime import datetime

try:
    from google.genai import types
    from google.genai.client import Client
    from google.genai.types import GenerateContentConfig, ToolConfig
    from google.genai.adk import LlmAgent, Session
    ADK_AVAILABLE = True
except ImportError:
    # For testing without ADK installed
    ADK_AVAILABLE = False
    LlmAgent = object
    Session = object

from nvidia_blog_agent.contracts.blog_models import RawBlogContent, BlogSummary
from nvidia_blog_agent.tools.summarization import build_summary_prompt, parse_summary_json


class SummarizerAgent(LlmAgent):
    """ADK LlmAgent that summarizes blog posts.
    
    This agent:
    1. Reads RawBlogContent objects from session.state (key: "raw_blog_contents")
    2. For each RawBlogContent, builds a prompt and calls the LLM
    3. Parses the LLM JSON response into BlogSummary objects
    4. Writes BlogSummary objects back to session.state (key: "blog_summaries")
    
    State Keys:
    - Input: "raw_blog_contents" (List[RawBlogContent])
    - Output: "blog_summaries" (List[BlogSummary])
    
    The agent uses Gemini for summarization and expects JSON responses
    that can be parsed into BlogSummary objects.
    """
    
    def __init__(
        self,
        *,
        model_name: str = "gemini-1.5-flash",
        max_text_chars: int = 4000,
        **kwargs
    ):
        """Initialize the SummarizerAgent.
        
        Args:
            model_name: Name of the Gemini model to use. Defaults to "gemini-1.5-flash".
            max_text_chars: Maximum characters from blog text to include in prompt.
                           Defaults to 4000.
            **kwargs: Additional arguments passed to LlmAgent.__init__.
        """
        if not ADK_AVAILABLE:
            raise ImportError(
                "google-genai-adk is required for SummarizerAgent. "
                "Install it with: pip install google-genai-adk"
            )
        
        super().__init__(
            name="SummarizerAgent",
            description="Summarizes NVIDIA tech blog posts into structured summaries.",
            model_name=model_name,
            **kwargs
        )
        self.max_text_chars = max_text_chars
    
    def process(self, session: Session) -> None:
        """Process RawBlogContent objects and generate BlogSummary objects.
        
        Reads RawBlogContent from session.state["raw_blog_contents"],
        generates summaries, and writes BlogSummary to session.state["blog_summaries"].
        
        Args:
            session: ADK Session object containing state.
        
        Raises:
            KeyError: If "raw_blog_contents" is not in session.state.
            ValueError: If LLM response cannot be parsed into BlogSummary.
        """
        # Read RawBlogContent objects from state
        raw_contents = session.state.get("raw_blog_contents", [])
        
        if not raw_contents:
            # No content to process
            session.state["blog_summaries"] = []
            return
        
        # Ensure raw_contents is a list
        if not isinstance(raw_contents, list):
            raise ValueError(
                f"Expected 'raw_blog_contents' to be a list, got {type(raw_contents)}"
            )
        
        summaries = []
        
        for raw_content in raw_contents:
            # Validate that it's a RawBlogContent object
            if not isinstance(raw_content, RawBlogContent):
                # Try to convert from dict if it's a dictionary
                if isinstance(raw_content, dict):
                    raw_content = RawBlogContent.model_validate(raw_content)
                else:
                    raise ValueError(
                        f"Expected RawBlogContent, got {type(raw_content)}"
                    )
            
            # Build prompt
            prompt = build_summary_prompt(raw_content, max_text_chars=self.max_text_chars)
            
            # Call LLM
            response = self.generate_content(prompt)
            
            # Extract text from response
            # ADK response format may vary, so we handle multiple cases
            if hasattr(response, 'text'):
                json_text = response.text
            elif isinstance(response, str):
                json_text = response
            elif hasattr(response, 'candidates') and response.candidates:
                # Handle GenerateContentResponse format
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    json_text = candidate.content.parts[0].text
                else:
                    json_text = str(candidate)
            else:
                json_text = str(response)
            
            # Parse JSON response into BlogSummary
            # Use published_at from RawBlogContent if available (would need to track BlogPost)
            # For now, we'll use None and let it be set from the original BlogPost if needed
            summary = parse_summary_json(
                raw_content,
                json_text,
                published_at=None  # Could be extracted from related BlogPost if stored
            )
            
            summaries.append(summary)
        
        # Write summaries back to state
        session.state["blog_summaries"] = summaries


# For testing: create a testable version that doesn't require ADK
class SummarizerAgentStub:
    """Stub implementation of SummarizerAgent for testing.
    
    This class provides the same interface as SummarizerAgent but uses
    a provided LLM function instead of the real ADK agent.
    """
    
    def __init__(
        self,
        llm_function,
        *,
        max_text_chars: int = 4000
    ):
        """Initialize the stub agent.
        
        Args:
            llm_function: Callable that takes a prompt string and returns JSON string.
            max_text_chars: Maximum characters from blog text to include in prompt.
        """
        self.llm_function = llm_function
        self.max_text_chars = max_text_chars
    
    def process(self, session: Any) -> None:
        """Process RawBlogContent objects using the stub LLM function.
        
        Args:
            session: Object with .state dict-like interface.
        """
        raw_contents = session.state.get("raw_blog_contents", [])
        
        if not raw_contents:
            session.state["blog_summaries"] = []
            return
        
        summaries = []
        
        for raw_content in raw_contents:
            if isinstance(raw_content, dict):
                raw_content = RawBlogContent.model_validate(raw_content)
            
            prompt = build_summary_prompt(raw_content, max_text_chars=self.max_text_chars)
            json_text = self.llm_function(prompt)
            summary = parse_summary_json(raw_content, json_text, published_at=None)
            summaries.append(summary)
        
        session.state["blog_summaries"] = summaries

