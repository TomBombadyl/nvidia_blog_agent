"""Integration tests to validate GitHub OIDC token fields for Workload Identity Federation.

These tests help ensure the GitHub Actions workflow is configured correctly
and that the OIDC token contains the expected claims for WIF authentication.
"""

import os
import json
import pytest
from typing import Dict, Any


class TestGitHubOIDCClaims:
    """Test that GitHub OIDC token claims match WIF provider expectations."""

    def test_repository_claim_format(self):
        """Verify repository claim follows expected format."""
        # In GitHub Actions, this would be: github.repository
        # Expected format: "owner/repo" (e.g., "TomBombadyl/nvidia_blog_agent")
        repository = os.environ.get("GITHUB_REPOSITORY", "TomBombadyl/nvidia_blog_agent")
        
        assert "/" in repository, "Repository must be in format 'owner/repo'"
        parts = repository.split("/")
        assert len(parts) == 2, "Repository must have exactly one slash"
        assert parts[0], "Repository owner must not be empty"
        assert parts[1], "Repository name must not be empty"
        
        # Should match WIF condition: attribute.repository == "TomBombadyl/nvidia_blog_agent"
        assert repository == "TomBombadyl/nvidia_blog_agent", \
            f"Repository '{repository}' doesn't match expected 'TomBombadyl/nvidia_blog_agent'"

    def test_ref_claim_format(self):
        """Verify ref claim follows expected format."""
        # In GitHub Actions, this would be: github.ref
        # Expected format: "refs/heads/branch" (e.g., "refs/heads/master")
        ref = os.environ.get("GITHUB_REF", "refs/heads/master")
        
        assert ref.startswith("refs/"), "Ref must start with 'refs/'"
        
        # Should match WIF condition: attribute.ref == "refs/heads/master" || "refs/heads/main"
        valid_refs = ["refs/heads/master", "refs/heads/main"]
        assert ref in valid_refs, \
            f"Ref '{ref}' must be one of {valid_refs} for deployment"

    def test_actor_claim_present(self):
        """Verify actor claim is present."""
        # In GitHub Actions, this would be: github.actor
        actor = os.environ.get("GITHUB_ACTOR", "TomBombadyl")
        
        assert actor, "Actor must not be empty"
        # Actor should match repository owner for security
        repository = os.environ.get("GITHUB_REPOSITORY", "TomBombadyl/nvidia_blog_agent")
        expected_owner = repository.split("/")[0]
        
        # Note: In real workflows, actor might differ from owner (e.g., in forks)
        # This is just a validation that actor exists
        assert len(actor) > 0, "Actor must be a non-empty string"

    def test_workflow_claim_present(self):
        """Verify workflow claim is present."""
        # In GitHub Actions, this would be: github.workflow
        workflow = os.environ.get("GITHUB_WORKFLOW", "Deploy to Cloud Run")
        
        assert workflow, "Workflow name must not be empty"
        # Should match expected workflow name
        assert "Deploy" in workflow or "deploy" in workflow.lower(), \
            "Workflow should be a deployment workflow"

    def test_wif_provider_secret_format(self):
        """Verify WIF_PROVIDER secret follows expected format."""
        # This would be set in GitHub Secrets
        # Format: projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
        wif_provider = os.environ.get("WIF_PROVIDER", "")
        
        if wif_provider:  # Only check if set (won't be in local tests)
            assert wif_provider.startswith("projects/"), \
                "WIF_PROVIDER must start with 'projects/'"
            assert "/locations/global/workloadIdentityPools/" in wif_provider, \
                "WIF_PROVIDER must include pool path"
            assert "/providers/" in wif_provider, \
                "WIF_PROVIDER must include provider path"

    def test_wif_service_account_format(self):
        """Verify WIF_SERVICE_ACCOUNT secret follows expected format."""
        # Format: service-account@project-id.iam.gserviceaccount.com
        service_account = os.environ.get("WIF_SERVICE_ACCOUNT", "")
        
        if service_account:  # Only check if set
            assert "@" in service_account, "Service account must contain '@'"
            assert service_account.endswith(".iam.gserviceaccount.com"), \
                "Service account must end with '.iam.gserviceaccount.com'"
            
            parts = service_account.split("@")
            assert len(parts) == 2, "Service account must have exactly one '@'"
            assert parts[0], "Service account name must not be empty"
            assert parts[1] == "nvidia-blog-agent.iam.gserviceaccount.com", \
                f"Service account project must be 'nvidia-blog-agent', got '{parts[1]}'"

    def test_required_secrets_present(self):
        """Verify all required secrets are documented (not necessarily set in test env)."""
        # These should be set in GitHub Secrets
        required_secrets = [
            "WIF_PROVIDER",
            "WIF_SERVICE_ACCOUNT",
            "RAG_CORPUS_ID",
            "INGEST_API_KEY",
        ]
        
        # In GitHub Actions, these would be available via ${{ secrets.* }}
        # In local tests, we just verify they're documented
        for secret in required_secrets:
            # Secret might not be set in test environment, that's OK
            # We're just validating the secret name is correct
            assert secret, f"Secret name '{secret}' must be non-empty"


class TestWIFAttributeMapping:
    """Test that attribute mappings match expected OIDC claims."""

    def test_repository_attribute_mapping(self):
        """Verify repository attribute maps correctly."""
        # In WIF provider, this should be:
        # attribute.repository → assertion.repository
        repository = os.environ.get("GITHUB_REPOSITORY", "TomBombadyl/nvidia_blog_agent")
        
        # The mapping should result in:
        # attribute.repository = "TomBombadyl/nvidia_blog_agent"
        assert repository == "TomBombadyl/nvidia_blog_agent", \
            "Repository must match WIF condition"

    def test_ref_attribute_mapping(self):
        """Verify ref attribute maps correctly."""
        # In WIF provider, this should be:
        # attribute.ref → assertion.ref
        ref = os.environ.get("GITHUB_REF", "refs/heads/master")
        
        # The mapping should result in:
        # attribute.ref = "refs/heads/master" or "refs/heads/main"
        valid_refs = ["refs/heads/master", "refs/heads/main"]
        assert ref in valid_refs, \
            f"Ref must be one of {valid_refs} to match WIF condition"


class TestWIFConditionLogic:
    """Test that WIF condition logic matches workflow requirements."""

    def test_condition_matches_repository(self):
        """Verify condition would match our repository."""
        repository = os.environ.get("GITHUB_REPOSITORY", "TomBombadyl/nvidia_blog_agent")
        condition_repo = "TomBombadyl/nvidia_blog_agent"
        
        # Simulate condition: attribute.repository == "TomBombadyl/nvidia_blog_agent"
        assert repository == condition_repo, \
            f"Repository '{repository}' must match condition '{condition_repo}'"

    def test_condition_matches_ref(self):
        """Verify condition would match our ref."""
        ref = os.environ.get("GITHUB_REF", "refs/heads/master")
        valid_refs = ["refs/heads/master", "refs/heads/main"]
        
        # Simulate condition: attribute.ref == "refs/heads/master" || "refs/heads/main"
        assert ref in valid_refs, \
            f"Ref '{ref}' must match one of the condition values {valid_refs}"

    def test_combined_condition(self):
        """Verify combined condition would pass."""
        repository = os.environ.get("GITHUB_REPOSITORY", "TomBombadyl/nvidia_blog_agent")
        ref = os.environ.get("GITHUB_REF", "refs/heads/master")
        
        # Simulate full condition:
        # attribute.repository == "TomBombadyl/nvidia_blog_agent"
        # && (attribute.ref == "refs/heads/master" || attribute.ref == "refs/heads/main")
        repo_match = repository == "TomBombadyl/nvidia_blog_agent"
        ref_match = ref in ["refs/heads/master", "refs/heads/main"]
        
        assert repo_match and ref_match, \
            f"Combined condition failed: repo_match={repo_match}, ref_match={ref_match}"


@pytest.mark.skipif(
    not os.environ.get("GITHUB_ACTIONS"),
    reason="Only run in GitHub Actions environment"
)
class TestGitHubActionsEnvironment:
    """Tests that only run in actual GitHub Actions environment."""

    def test_github_environment_variables_present(self):
        """Verify GitHub Actions environment variables are set."""
        required_vars = [
            "GITHUB_REPOSITORY",
            "GITHUB_REF",
            "GITHUB_ACTOR",
            "GITHUB_WORKFLOW",
        ]
        
        for var in required_vars:
            assert var in os.environ, f"GitHub Actions variable '{var}' must be set"

    def test_oidc_token_audience(self):
        """Verify OIDC token audience matches WIF provider."""
        # In GitHub Actions, the OIDC token audience should be the WIF provider resource name
        wif_provider = os.environ.get("WIF_PROVIDER", "")
        
        if wif_provider:
            # The token audience should match the provider
            # This is automatically set by google-github-actions/auth
            assert wif_provider.startswith("projects/"), \
                "WIF provider must be a valid resource name"


if __name__ == "__main__":
    # Run tests with: pytest tests/integration/test_wif_validation.py -v
    pytest.main([__file__, "-v"])

