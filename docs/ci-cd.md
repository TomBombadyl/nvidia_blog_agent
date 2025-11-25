# CI/CD Pipeline Documentation

This project uses GitHub Actions for continuous integration and deployment.

## Workflows

### 1. CI Workflow (`.github/workflows/ci.yml`)

Runs on every push and pull request to `master`/`main` branches.

**Jobs:**
- **Test**: Runs tests across Python 3.10, 3.11, and 3.12
  - Installs dependencies
  - Runs pytest with coverage
  - Uploads coverage reports to Codecov
  
- **Lint**: Code quality checks
  - Runs `ruff` linter
  - Checks code formatting with `ruff format`
  - Runs `mypy` type checking (non-blocking)
  
- **Build**: Docker image build verification
  - Builds Docker image without pushing
  - Verifies Dockerfile is valid
  - Uses build cache for faster builds

### 2. Deploy Workflow (`.github/workflows/deploy.yml`)

Runs on pushes to `master`/`main` (excluding documentation changes) or manual trigger.

**Jobs:**
- **Test**: Runs full test suite before deployment
- **Deploy**: Deploys to Google Cloud Run
  - Authenticates with Google Cloud
  - Builds and pushes Docker image to Artifact Registry
  - Deploys to Cloud Run with environment variables
  - Performs health check after deployment

**Manual Deployment:**
```bash
# Trigger via GitHub Actions UI or:
gh workflow run deploy.yml -f skip_tests=false
```

### 3. Release Workflow (`.github/workflows/release.yml`)

Runs when a version tag is pushed (e.g., `v1.0.0`).

**Actions:**
- Creates GitHub Release
- Generates changelog from git commits
- Tags the release

## Required GitHub Secrets

Configure these in GitHub repository settings → Secrets and variables → Actions:

1. **GCP_SA_KEY**: Service account JSON key for Google Cloud authentication
   ```bash
   # Get from service account:
   gcloud iam service-accounts keys create key.json \
     --iam-account=nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com
   # Copy contents to GitHub secret
   ```

2. **RAG_CORPUS_ID**: Vertex AI RAG corpus ID
   - Get from Vertex AI RAG Engine console
   - Example: `6917529027641081856`

3. **INGEST_API_KEY**: API key for `/ingest` endpoint
   - Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - Must match the key set in Cloud Run environment variables

## Workflow Triggers

### Automatic Triggers

- **CI**: Runs on every push/PR
- **Deploy**: Runs on push to `master`/`main` (excluding docs)

### Manual Triggers

- **Deploy**: Can be triggered manually via GitHub Actions UI
  - Option to skip tests (not recommended)

### Tag-Based Triggers

- **Release**: Push a tag like `v1.0.0` to create a release

## Branch Protection

Recommended branch protection rules for `master`/`main`:

1. Require status checks to pass before merging
   - `test (3.10)`
   - `test (3.11)`
   - `test (3.12)`
   - `lint`
   - `build`

2. Require branches to be up to date before merging

3. Require pull request reviews

## Local Testing

Test workflows locally using [act](https://github.com/nektos/act):

```bash
# Install act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Test CI workflow
act -j test

# Test deploy workflow (requires secrets)
act -j deploy --secret-file .secrets
```

## Troubleshooting

### Tests Fail in CI

- Check Python version compatibility
- Verify all dependencies are in `requirements.txt`
- Check for environment-specific issues

### Deployment Fails

- Verify `GCP_SA_KEY` secret is correct
- Check service account has required permissions
- Verify `RAG_CORPUS_ID` and `INGEST_API_KEY` secrets are set
- Check Cloud Run logs: `gcloud logging read ...`

### Docker Build Fails

- Verify Dockerfile syntax
- Check for missing files in build context
- Review build logs for specific errors

## Best Practices

1. **Always run tests locally** before pushing
2. **Review CI results** before merging PRs
3. **Use feature branches** for development
4. **Tag releases** for production deployments
5. **Monitor deployment health** after each deploy
6. **Keep secrets secure** - never commit them

## Workflow Status Badge

Add to README.md:

```markdown
![CI](https://github.com/USERNAME/nvidia_blog_agent/workflows/CI/badge.svg)
![Deploy](https://github.com/USERNAME/nvidia_blog_agent/workflows/Deploy%20to%20Cloud%20Run/badge.svg)
```

