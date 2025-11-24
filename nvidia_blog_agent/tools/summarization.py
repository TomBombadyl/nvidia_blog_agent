"""Summarization tools for converting RawBlogContent to BlogSummary.

This module provides:
- build_summary_prompt(): Constructs a prompt for LLM summarization
- parse_summary_json(): Parses LLM JSON response into BlogSummary

These functions are pure and deterministic, making them easy to test
and integrate with various LLM providers.
"""

import json
import re
from typing import Optional
from datetime import datetime
from nvidia_blog_agent.contracts.blog_models import RawBlogContent, BlogSummary


def build_summary_prompt(raw: RawBlogContent, *, max_text_chars: int = 4000) -> str:
    """Build a prompt for summarizing a blog post into structured JSON.
    
    The prompt instructs the LLM to return strict JSON with:
    - executive_summary: High-level summary (1-3 sentences)
    - technical_summary: Detailed technical summary (2-5 paragraphs)
    - bullet_points: List of key takeaways
    - keywords: List of relevant keywords/topics
    
    Args:
        raw: RawBlogContent object containing the blog post content.
        max_text_chars: Maximum number of characters to include from raw.text.
                        Defaults to 4000. Text will be truncated if longer.
    
    Returns:
        A formatted prompt string ready to send to an LLM.
    
    Example:
        >>> raw = RawBlogContent(
        ...     blog_id="test-id",
        ...     url="https://example.com/post",
        ...     title="Test Post",
        ...     html="<html>...</html>",
        ...     text="This is a blog post about AI and machine learning...",
        ...     sections=["Introduction", "Main Content"]
        ... )
        >>> prompt = build_summary_prompt(raw)
        >>> assert "Test Post" in prompt
        >>> assert "executive_summary" in prompt.lower()
    """
    # Truncate text if necessary
    text_to_summarize = raw.text
    if len(text_to_summarize) > max_text_chars:
        text_to_summarize = text_to_summarize[:max_text_chars] + "..."
    
    # Build sections text if available
    sections_text = ""
    if raw.sections:
        sections_text = "\n\n".join(f"Section {i+1}:\n{section}" 
                                   for i, section in enumerate(raw.sections))
    
    prompt = f"""You are an expert technical writer summarizing NVIDIA technical blog posts.

Please analyze the following blog post and provide a comprehensive summary in JSON format.

Blog Post Title: {raw.title}
Blog Post URL: {raw.url}

Content:
{text_to_summarize}
"""
    
    if sections_text:
        prompt += f"""

Structured Sections:
{sections_text}
"""
    
    prompt += """

Please provide a summary in the following JSON format (strict JSON, no markdown, no code blocks):

{
  "executive_summary": "A high-level executive summary in 1-3 sentences that captures the main purpose and value of this blog post.",
  "technical_summary": "A detailed technical summary in 2-5 paragraphs that explains the key concepts, methodologies, implementation details, and technical insights discussed in the blog post.",
  "bullet_points": [
    "Key takeaway 1",
    "Key takeaway 2",
    "Key takeaway 3"
  ],
  "keywords": [
    "keyword1",
    "keyword2",
    "keyword3"
  ]
}

Requirements:
- executive_summary: Must be at least 10 characters. Should be concise and accessible to non-technical readers.
- technical_summary: Must be at least 50 characters. Should provide sufficient technical detail for engineers and researchers.
- bullet_points: Array of strings, each representing a key takeaway. Can be empty array if no specific points.
- keywords: Array of strings, each representing a relevant keyword or topic. Should be lowercase. Can be empty array.

Return ONLY valid JSON. Do not include any markdown formatting, code block markers, or explanatory text outside the JSON object.
"""
    
    return prompt


def parse_summary_json(
    raw: RawBlogContent,
    json_text: str,
    published_at: Optional[datetime] = None
) -> BlogSummary:
    """Parse LLM JSON response into a BlogSummary object.
    
    This function handles common LLM response formats:
    - JSON wrapped in markdown code blocks (```json ... ```)
    - JSON with leading/trailing whitespace
    - Plain JSON strings
    
    Args:
        raw: RawBlogContent object used to generate the summary.
        json_text: JSON string response from the LLM (may include markdown formatting).
        published_at: Optional publication timestamp. If None, will be None in BlogSummary.
    
    Returns:
        BlogSummary object with parsed data.
    
    Raises:
        ValueError: If JSON cannot be parsed or required fields are missing.
        ValidationError: If parsed data doesn't meet BlogSummary validation requirements.
    
    Example:
        >>> raw = RawBlogContent(
        ...     blog_id="test-id",
        ...     url="https://example.com/post",
        ...     title="Test Post",
        ...     html="<html>...</html>",
        ...     text="Content here"
        ... )
        >>> json_str = '{"executive_summary": "Summary", "technical_summary": "Detailed technical summary with enough content to meet validation requirements.", "bullet_points": [], "keywords": []}'
        >>> summary = parse_summary_json(raw, json_str)
        >>> summary.blog_id == "test-id"
        True
    """
    # Clean the JSON text - remove markdown code blocks if present
    cleaned_json = json_text.strip()
    
    # Remove markdown code block markers (```json ... ``` or ``` ... ```)
    if cleaned_json.startswith("```"):
        # Find the first newline after ```
        first_newline = cleaned_json.find("\n")
        if first_newline != -1:
            cleaned_json = cleaned_json[first_newline:].strip()
        # Remove trailing ```
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3].strip()
    
    # Try to extract JSON if it's wrapped in other text
    # Look for JSON object pattern: { ... }
    json_match = re.search(r'\{.*\}', cleaned_json, re.DOTALL)
    if json_match:
        cleaned_json = json_match.group(0)
    
    # Parse JSON
    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from LLM response: {e}. Response was: {json_text[:200]}...")
    
    # Extract fields with validation
    executive_summary = data.get("executive_summary", "")
    technical_summary = data.get("technical_summary", "")
    bullet_points = data.get("bullet_points", [])
    keywords = data.get("keywords", [])
    
    # Ensure bullet_points and keywords are lists
    if not isinstance(bullet_points, list):
        bullet_points = []
    if not isinstance(keywords, list):
        keywords = []
    
    # Create BlogSummary
    return BlogSummary(
        blog_id=raw.blog_id,
        title=raw.title,
        url=raw.url,
        published_at=published_at,
        executive_summary=executive_summary,
        technical_summary=technical_summary,
        bullet_points=bullet_points,
        keywords=keywords
    )

