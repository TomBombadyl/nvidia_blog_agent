"""QA Agent for answering questions using RAG retrieval and LLM generation.

This module provides:
- QaModelLike Protocol: Abstract interface for answer generation models
- QAAgent: Question-answering agent that retrieves docs and generates answers

The QA agent:
1. Accepts a natural-language question
2. Uses RagRetrieveClient to retrieve relevant documents
3. Uses QaModelLike to generate an answer grounded in those documents
4. Returns both the answer text and the retrieved documents used

The agent is designed to be testable and can be wrapped by ADK workflows in later phases.
"""

from typing import Protocol, List, Tuple
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.tools.rag_retrieve import RagRetrieveClient


class QaModelLike(Protocol):
    """Protocol for answer generation models.

    This abstract interface allows the QA agent to work with various model implementations:
    - ADK LlmAgent / Gemini models
    - Other LLM providers
    - Test doubles for testing

    Implementations of this protocol must provide a generate_answer method.
    """

    def generate_answer(self, question: str, docs: List[RetrievedDoc]) -> str:
        """Generate an answer to a question based on retrieved documents.

        Args:
            question: The user's question string.
            docs: List of RetrievedDoc objects to use as context for answering.

        Returns:
            Answer string generated based on the question and documents.
        """
        ...


class QAAgent:
    """Question-answering agent that uses RAG retrieval and LLM generation.

    This agent combines document retrieval with answer generation to provide
    answers grounded in the RAG backend. It handles cases where no documents
    are found gracefully.

    Example:
        >>> from nvidia_blog_agent.tools.rag_retrieve import HttpRagRetrieveClient
        >>> from nvidia_blog_agent.agents.qa_agent import QAAgent
        >>>
        >>> rag_client = HttpRagRetrieveClient(
        ...     base_url="https://rag.example.com",
        ...     uuid="corpus-123"
        ... )
        >>> model = SomeQaModel()  # Implements QaModelLike
        >>> agent = QAAgent(rag_client, model)
        >>>
        >>> answer, docs = await agent.answer("What is RAG?")
        >>> print(answer)
    """

    def __init__(self, rag_client: RagRetrieveClient, model: QaModelLike):
        """Initialize the QA agent.

        Args:
            rag_client: RAG retrieval client for fetching relevant documents.
            model: Answer generation model that implements QaModelLike.
        """
        self._rag_client = rag_client
        self._model = model

    async def answer(self, question: str, k: int = 5) -> Tuple[str, List[RetrievedDoc]]:
        """Retrieve documents and generate an answer to the question.

        This method:
        1. Calls the RAG client to retrieve relevant documents
        2. If no documents are found, returns a conservative "I don't know" answer
        3. If documents are found, calls the model to generate an answer
        4. Returns both the answer text and the retrieved documents

        Args:
            question: The user's natural-language question.
            k: Maximum number of documents to retrieve. Defaults to 5.

        Returns:
            Tuple of (answer_text, retrieved_docs), where:
            - answer_text: The generated answer string
            - retrieved_docs: List of RetrievedDoc objects used to form the answer
                              (empty list if no documents were found)

        Example:
            >>> answer, docs = await agent.answer("What did NVIDIA say about RAG?")
            >>> print(answer)
            "Based on the NVIDIA blog posts..."
            >>> len(docs)
            3
        """
        # Retrieve relevant documents
        docs = await self._rag_client.retrieve(question, k=k)

        # Handle case where no documents are found
        if not docs:
            return (
                "I couldn't find any NVIDIA blog posts related to that question. "
                "Please try rephrasing your question or asking about a different topic.",
                [],
            )

        # Generate answer using the model
        answer_text = self._model.generate_answer(question, docs)

        return (answer_text, docs)
