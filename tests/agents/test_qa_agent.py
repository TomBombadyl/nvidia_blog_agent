"""Unit tests for QA Agent.

Tests cover:
- Normal case with retrieved documents
- No documents case
- Custom k value
- Integration with RagRetrieveClient and QaModelLike
"""

import pytest
from typing import List
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.agents.qa_agent import QAAgent


class StubRagClient:
    """Stub implementation of RagRetrieveClient for testing."""

    def __init__(self, docs: List[RetrievedDoc]):
        """Initialize stub with predefined documents.

        Args:
            docs: List of RetrievedDoc objects to return on retrieve() calls.
        """
        self.docs = docs
        self.queries: List[tuple[str, int]] = []

    async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
        """Retrieve documents (stub implementation).

        Args:
            query: The search query (recorded for testing).
            k: Maximum number of documents (recorded for testing).

        Returns:
            The predefined docs list.
        """
        self.queries.append((query, k))
        return self.docs


class StubQaModel:
    """Stub implementation of QaModelLike for testing."""

    def __init__(self):
        """Initialize stub model."""
        self.calls: List[tuple[str, List[RetrievedDoc]]] = []

    def generate_answer(self, question: str, docs: List[RetrievedDoc]) -> str:
        """Generate answer (stub implementation).

        Args:
            question: The question (recorded for testing).
            docs: The documents (recorded for testing).

        Returns:
            A simple synthetic answer based on document titles.
        """
        self.calls.append((question, docs))
        if not docs:
            return "No answer available."
        titles = ", ".join(d.title for d in docs)
        return f"Answer based on: {titles}"


class TestQAAgent:
    """Tests for QAAgent."""

    @pytest.mark.asyncio
    async def test_normal_case_with_docs(self):
        """Test normal case where documents are retrieved."""
        # Prepare RetrievedDoc instances
        doc1 = RetrievedDoc(
            blog_id="id-1",
            title="NVIDIA RAG Blog Post",
            url="https://developer.nvidia.com/blog/rag",
            snippet="RAG is a technique for retrieval-augmented generation.",
            score=0.95,
            metadata={"source": "nvidia_tech_blog"},
        )
        doc2 = RetrievedDoc(
            blog_id="id-2",
            title="CUDA Programming Guide",
            url="https://developer.nvidia.com/blog/cuda",
            snippet="CUDA enables parallel computing on GPUs.",
            score=0.82,
            metadata={"source": "nvidia_tech_blog"},
        )

        # Create stubs
        rag_client = StubRagClient([doc1, doc2])
        model = StubQaModel()

        # Create agent
        agent = QAAgent(rag_client, model)

        # Call answer
        answer, docs = await agent.answer("What did NVIDIA say about RAG?")

        # Assertions
        assert len(rag_client.queries) == 1
        assert rag_client.queries[0][0] == "What did NVIDIA say about RAG?"
        assert rag_client.queries[0][1] == 5  # Default k

        assert len(model.calls) == 1
        assert model.calls[0][0] == "What did NVIDIA say about RAG?"
        assert model.calls[0][1] == [doc1, doc2]

        assert answer == "Answer based on: NVIDIA RAG Blog Post, CUDA Programming Guide"
        assert docs == [doc1, doc2]

    @pytest.mark.asyncio
    async def test_no_docs_case(self):
        """Test case where no documents are retrieved."""
        # Create stubs with empty docs
        rag_client = StubRagClient([])
        model = StubQaModel()

        # Create agent
        agent = QAAgent(rag_client, model)

        # Call answer
        answer, docs = await agent.answer("What is quantum computing?")

        # Assertions
        assert len(rag_client.queries) == 1
        assert rag_client.queries[0][0] == "What is quantum computing?"

        # Model should NOT be called when no docs
        assert len(model.calls) == 0

        # Should return conservative answer
        assert "couldn't find any" in answer.lower() or "no relevant" in answer.lower()
        assert docs == []

    @pytest.mark.asyncio
    async def test_custom_k_value(self):
        """Test that custom k value is passed to retrieval client."""
        doc1 = RetrievedDoc(
            blog_id="id-1",
            title="Test Post",
            url="https://example.com/post",
            snippet="Test content",
            score=0.8,
            metadata={},
        )

        rag_client = StubRagClient([doc1])
        model = StubQaModel()

        agent = QAAgent(rag_client, model)

        # Call with custom k
        answer, docs = await agent.answer("test question", k=10)

        # Assert k was passed correctly
        assert len(rag_client.queries) == 1
        assert rag_client.queries[0][1] == 10

        # Model should be called
        assert len(model.calls) == 1
        assert answer is not None
        assert docs == [doc1]

    @pytest.mark.asyncio
    async def test_single_doc_case(self):
        """Test case with a single retrieved document."""
        doc = RetrievedDoc(
            blog_id="id-1",
            title="Single Blog Post",
            url="https://example.com/post",
            snippet="Single document content",
            score=0.9,
            metadata={},
        )

        rag_client = StubRagClient([doc])
        model = StubQaModel()

        agent = QAAgent(rag_client, model)

        answer, docs = await agent.answer("What is this about?")

        assert len(model.calls) == 1
        assert model.calls[0][1] == [doc]
        assert answer == "Answer based on: Single Blog Post"
        assert docs == [doc]

    @pytest.mark.asyncio
    async def test_model_receives_correct_docs(self):
        """Test that model receives the exact docs returned by retrieval."""
        doc1 = RetrievedDoc(
            blog_id="id-1",
            title="Doc 1",
            url="https://example.com/1",
            snippet="Content 1",
            score=0.9,
            metadata={},
        )
        doc2 = RetrievedDoc(
            blog_id="id-2",
            title="Doc 2",
            url="https://example.com/2",
            snippet="Content 2",
            score=0.8,
            metadata={},
        )
        doc3 = RetrievedDoc(
            blog_id="id-3",
            title="Doc 3",
            url="https://example.com/3",
            snippet="Content 3",
            score=0.7,
            metadata={},
        )

        rag_client = StubRagClient([doc1, doc2, doc3])
        model = StubQaModel()

        agent = QAAgent(rag_client, model)

        answer, docs = await agent.answer("test", k=3)

        # Verify model received all three docs
        assert len(model.calls[0][1]) == 3
        assert model.calls[0][1][0] == doc1
        assert model.calls[0][1][1] == doc2
        assert model.calls[0][1][2] == doc3

        # Verify returned docs match
        assert docs == [doc1, doc2, doc3]

    @pytest.mark.asyncio
    async def test_multiple_queries(self):
        """Test that agent can handle multiple queries."""
        doc1 = RetrievedDoc(
            blog_id="id-1",
            title="Doc 1",
            url="https://example.com/1",
            snippet="Content 1",
            score=0.9,
            metadata={},
        )

        rag_client = StubRagClient([doc1])
        model = StubQaModel()

        agent = QAAgent(rag_client, model)

        # First query
        answer1, docs1 = await agent.answer("Question 1")

        # Second query
        answer2, docs2 = await agent.answer("Question 2")

        # Verify both queries were recorded
        assert len(rag_client.queries) == 2
        assert rag_client.queries[0][0] == "Question 1"
        assert rag_client.queries[1][0] == "Question 2"

        # Verify model was called twice
        assert len(model.calls) == 2
        assert model.calls[0][0] == "Question 1"
        assert model.calls[1][0] == "Question 2"
