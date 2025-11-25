"""Regression tests for the evaluation harness.

Tests cover:
- All-pass evaluation scenarios
- Partial-failure scenarios
- Case-insensitivity of substring matching
- Edge cases (empty cases, empty answers, etc.)
"""

import pytest
from typing import List
from nvidia_blog_agent.contracts.blog_models import RetrievedDoc
from nvidia_blog_agent.agents.qa_agent import QAAgent, QaModelLike
from nvidia_blog_agent.eval.harness import (
    EvalCase,
    EvalResult,
    EvalSummary,
    simple_pass_fail_checker,
    run_qa_evaluation,
    summarize_eval_results,
)


class StubQAAgent(QAAgent):
    """Stub QAAgent for regression testing.
    
    This stub bypasses the real RAG retrieval and model, returning
    predetermined answers based on the question.
    """
    
    def __init__(self, answers_by_question: dict[str, str]):
        """Initialize stub agent with predetermined answers.
        
        Args:
            answers_by_question: Dictionary mapping question strings to answer strings.
        """
        # Create a dummy RAG client and model (won't be used)
        from nvidia_blog_agent.tools.rag_retrieve import RagRetrieveClient
        
        class DummyRagClient(RagRetrieveClient):
            async def retrieve(self, query: str, k: int = 5) -> List[RetrievedDoc]:
                return []
        
        class DummyModel(QaModelLike):
            def generate_answer(self, question: str, docs: List[RetrievedDoc]) -> str:
                return answers_by_question.get(question, "")
        
        super().__init__(rag_client=DummyRagClient(), model=DummyModel())
        self.answers_by_question = answers_by_question
        self.calls: List[tuple[str, int]] = []
    
    async def answer(self, question: str, k: int = 5) -> tuple[str, List[RetrievedDoc]]:
        """Answer a question (stub implementation).
        
        Args:
            question: The question string.
            k: Maximum number of documents (recorded but not used).
        
        Returns:
            Tuple of (answer_text, empty_docs_list).
        """
        self.calls.append((question, k))
        answer = self.answers_by_question.get(question, "")
        return answer, []


class TestSimplePassFailChecker:
    """Tests for simple_pass_fail_checker function."""
    
    def test_all_substrings_match(self):
        """Test that checker passes when all substrings match."""
        answer = "This is about NVIDIA RAG technology and GPU acceleration"
        expected = ["NVIDIA", "RAG", "GPU"]
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is True
        assert len(matched) == 3
        assert all(s in matched for s in expected)
    
    def test_some_substrings_match(self):
        """Test that checker fails when only some substrings match."""
        answer = "This is about NVIDIA technology"
        expected = ["NVIDIA", "RAG", "GPU"]
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is False
        assert len(matched) == 1
        assert "NVIDIA" in matched
    
    def test_no_substrings_match(self):
        """Test that checker fails when no substrings match."""
        answer = "This is about something else"
        expected = ["NVIDIA", "RAG"]
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is False
        assert len(matched) == 0
    
    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        answer = "This is about nvidia rag technology"
        expected = ["NVIDIA", "RAG"]
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is True
        assert len(matched) == 2
    
    def test_empty_expected_substrings(self):
        """Test that empty expected_substrings always passes."""
        answer = "Any answer"
        expected = []
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is True
        assert len(matched) == 0
    
    def test_empty_answer(self):
        """Test that empty answer fails if substrings are expected."""
        answer = ""
        expected = ["NVIDIA"]
        
        passed, matched = simple_pass_fail_checker(answer, expected)
        
        assert passed is False
        assert len(matched) == 0


class TestRunQAEvaluation:
    """Tests for run_qa_evaluation function."""
    
    @pytest.mark.asyncio
    async def test_all_pass_scenario(self):
        """Test evaluation with all cases passing."""
        answers = {
            "What is RAG?": "RAG stands for Retrieval-Augmented Generation and is used in AI systems.",
            "What is GPU?": "GPU stands for Graphics Processing Unit and accelerates computation.",
        }
        
        qa_agent = StubQAAgent(answers)
        
        cases = [
            EvalCase(
                question="What is RAG?",
                expected_substrings=["RAG", "Retrieval"],
                max_docs=5,
            ),
            EvalCase(
                question="What is GPU?",
                expected_substrings=["GPU", "Graphics"],
                max_docs=5,
            ),
        ]
        
        results = await run_qa_evaluation(qa_agent, cases)
        
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert results[0].question == "What is RAG?"
        assert results[1].question == "What is GPU?"
        assert len(results[0].matched_substrings) == 2
        assert len(results[1].matched_substrings) == 2
    
    @pytest.mark.asyncio
    async def test_partial_failure_scenario(self):
        """Test evaluation with some cases failing."""
        answers = {
            "What is RAG?": "RAG stands for Retrieval-Augmented Generation.",
            "What is GPU?": "GPU is a processor.",  # Missing "Graphics"
        }
        
        qa_agent = StubQAAgent(answers)
        
        cases = [
            EvalCase(
                question="What is RAG?",
                expected_substrings=["RAG", "Retrieval"],
                max_docs=5,
            ),
            EvalCase(
                question="What is GPU?",
                expected_substrings=["GPU", "Graphics"],  # Will fail
                max_docs=5,
            ),
        ]
        
        results = await run_qa_evaluation(qa_agent, cases)
        
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False
        assert len(results[1].matched_substrings) == 1  # Only "GPU" matched
    
    @pytest.mark.asyncio
    async def test_case_insensitivity(self):
        """Test that evaluation is case-insensitive."""
        answers = {
            "What is RAG?": "rag is a technology for retrieval augmented generation",
        }
        
        qa_agent = StubQAAgent(answers)
        
        cases = [
            EvalCase(
                question="What is RAG?",
                expected_substrings=["RAG", "RETRIEVAL"],  # Uppercase
                max_docs=5,
            ),
        ]
        
        results = await run_qa_evaluation(qa_agent, cases)
        
        assert len(results) == 1
        assert results[0].passed is True
        assert len(results[0].matched_substrings) == 2
    
    @pytest.mark.asyncio
    async def test_empty_cases_list(self):
        """Test that empty cases list returns empty results."""
        qa_agent = StubQAAgent({})
        
        results = await run_qa_evaluation(qa_agent, [])
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_missing_answer(self):
        """Test that missing answer (empty string) fails."""
        qa_agent = StubQAAgent({})  # No answers
        
        cases = [
            EvalCase(
                question="Unknown question?",
                expected_substrings=["answer"],
                max_docs=5,
            ),
        ]
        
        results = await run_qa_evaluation(qa_agent, cases)
        
        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].answer == ""
        assert len(results[0].matched_substrings) == 0
    
    @pytest.mark.asyncio
    async def test_custom_max_docs(self):
        """Test that custom max_docs is passed to agent."""
        qa_agent = StubQAAgent({"Q": "Answer"})
        
        cases = [
            EvalCase(
                question="Q",
                expected_substrings=["Answer"],
                max_docs=10,
            ),
        ]
        
        await run_qa_evaluation(qa_agent, cases)
        
        assert len(qa_agent.calls) == 1
        assert qa_agent.calls[0][1] == 10  # k parameter


class TestSummarizeEvalResults:
    """Tests for summarize_eval_results function."""
    
    def test_all_pass_summary(self):
        """Test summary when all cases pass."""
        results = [
            EvalResult(
                question="Q1",
                answer="A1",
                retrieved_docs=[],
                passed=True,
                matched_substrings=["test"],
            ),
            EvalResult(
                question="Q2",
                answer="A2",
                retrieved_docs=[],
                passed=True,
                matched_substrings=["test"],
            ),
        ]
        
        summary = summarize_eval_results(results)
        
        assert summary.total == 2
        assert summary.passed == 2
        assert summary.failed == 0
        assert summary.pass_rate == 1.0
    
    def test_partial_failure_summary(self):
        """Test summary when some cases fail."""
        results = [
            EvalResult(
                question="Q1",
                answer="A1",
                retrieved_docs=[],
                passed=True,
                matched_substrings=["test"],
            ),
            EvalResult(
                question="Q2",
                answer="A2",
                retrieved_docs=[],
                passed=False,
                matched_substrings=[],
            ),
            EvalResult(
                question="Q3",
                answer="A3",
                retrieved_docs=[],
                passed=False,
                matched_substrings=[],
            ),
        ]
        
        summary = summarize_eval_results(results)
        
        assert summary.total == 3
        assert summary.passed == 1
        assert summary.failed == 2
        assert summary.pass_rate == pytest.approx(1.0 / 3.0)
    
    def test_all_fail_summary(self):
        """Test summary when all cases fail."""
        results = [
            EvalResult(
                question="Q1",
                answer="A1",
                retrieved_docs=[],
                passed=False,
                matched_substrings=[],
            ),
            EvalResult(
                question="Q2",
                answer="A2",
                retrieved_docs=[],
                passed=False,
                matched_substrings=[],
            ),
        ]
        
        summary = summarize_eval_results(results)
        
        assert summary.total == 2
        assert summary.passed == 0
        assert summary.failed == 2
        assert summary.pass_rate == 0.0
    
    def test_empty_results_summary(self):
        """Test summary with empty results list."""
        summary = summarize_eval_results([])
        
        assert summary.total == 0
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.pass_rate == 0.0

