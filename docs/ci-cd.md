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

1. **WIF_PROVIDER**: Workload Identity Federation provider resource name
   - Format: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID`
   - Get from: GCP Console → IAM & Admin → Workload Identity Federation
   - See [Workload Identity Federation Guide](workload-identity-federation.md) for setup

2. **WIF_SERVICE_ACCOUNT**: Service account email for Workload Identity
   - Format: `nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com`
   - Must have `roles/iam.workloadIdentityUser` role on the provider

3. **GCP_PROJECT_ID**: (Optional) GCP project ID
   - Defaults to `nvidia-blog-agent` if not set

4. **RAG_CORPUS_ID**: Vertex AI RAG corpus ID
   - Get from Vertex AI RAG Engine console
   - Example: `6917529027641081856`

5. **INGEST_API_KEY**: API key for `/ingest` endpoint
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

This section provides comprehensive troubleshooting guidance for common CI/CD issues.

### Quick Diagnostics

#### Check Workflow Status

1. Go to GitHub Actions: `https://github.com/TomBombadyl/nvidia_blog_agent/actions`
2. Click on the failing workflow run
3. Expand the failing job to see error details

#### Common Error Patterns

| Error Pattern | Likely Cause | Solution |
|--------------|--------------|----------|
| `unauthorized_client` | Workload Identity Provider condition mismatch | See [Workload Identity Federation Guide](workload-identity-federation.md) |
| `permission denied` | Service account missing IAM roles | Check service account permissions |
| `image not found` | Docker build failed or image not pushed | Check build logs |
| `test failures` | Code issues or dependency problems | Run tests locally first |
| `linting errors` | Code style violations | Run `ruff check` and `ruff format` |

### Authentication Issues

#### Workload Identity Federation Errors

**Error**: `failed to generate Google Cloud federated token ... {"error":"unauthorized_client"}`

**Diagnosis**:
1. GitHub issued OIDC token ✅
2. Google Cloud received token ✅
3. Provider condition rejected it ❌

**Fix**: See [Workload Identity Federation Guide](workload-identity-federation.md) for detailed troubleshooting

**Quick Check**:
```bash
# Verify provider condition matches your repo
# In GCP Console: IAM & Admin → Workload Identity Federation
# Condition should include:
attribute.repository == "TomBombadyl/nvidia_blog_agent"
```

#### Service Account Permission Errors

**Error**: `Permission denied on resource` or `does not have required permission`

**Diagnosis**:
- Service account missing required IAM roles
- Workload Identity User binding incorrect

**Fix**:
```bash
# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding nvidia-blog-agent \
  --member="serviceAccount:nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Grant Service Account User role
gcloud projects add-iam-policy-binding nvidia-blog-agent \
  --member="serviceAccount:nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Verify Workload Identity User binding
gcloud iam service-accounts get-iam-policy \
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com
```

### Build and Deployment Issues

#### Docker Build Failures

**Error**: `failed to solve: failed to compute cache key` or `COPY failed`

**Diagnosis**:
- Missing files in build context
- Dockerfile syntax error
- Network issues pulling base image

**Fix**:
1. Verify Dockerfile syntax:
   ```bash
   docker build -t test-image .
   ```

2. Check build context includes all required files:
   ```bash
   # Ensure these files exist:
   - Dockerfile
   - requirements.txt
   - pyproject.toml
   - nvidia_blog_agent/ (package)
   - service/ (FastAPI app)
   ```

3. Test locally:
   ```bash
   docker build -t nvidia-blog-agent:test .
   docker run -p 8080:8080 nvidia-blog-agent:test
   ```

#### Image Push Failures

**Error**: `unauthorized: You don't have the required permissions`

**Diagnosis**:
- Artifact Registry permissions missing
- Docker not authenticated

**Fix**:
```bash
# Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Verify service account has Artifact Registry Writer role
gcloud projects add-iam-policy-binding nvidia-blog-agent \
  --member="serviceAccount:nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

#### Cloud Run Deployment Failures

**Error**: `Revision failed with message: Container failed to start`

**Diagnosis**:
- Application crash on startup
- Missing environment variables
- Health check failing

**Fix**:
1. Check Cloud Run logs:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" \
     --limit 50 \
     --format json
   ```

2. Verify environment variables are set:
   ```bash
   gcloud run services describe nvidia-blog-agent \
     --region us-central1 \
     --format="value(spec.template.spec.containers[0].env)"
   ```

3. Test locally with same environment:
   ```bash
   export GOOGLE_CLOUD_PROJECT=nvidia-blog-agent
   export USE_VERTEX_RAG=true
   export RAG_CORPUS_ID=YOUR_CORPUS_ID
   # ... other env vars
   python -m service.app
   ```

### Test Failures

#### Python Version Mismatch

**Error**: Tests pass locally but fail in CI

**Diagnosis**:
- Different Python versions
- Dependency version conflicts

**Fix**:
1. Match local Python version to CI:
   ```bash
   # CI uses: 3.10, 3.11, 3.12
   python --version  # Should match one of these
   ```

2. Use virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -e .
   pytest
   ```

#### Missing Dependencies

**Error**: `ModuleNotFoundError` or `ImportError`

**Diagnosis**:
- Dependency not in `requirements.txt` or `pyproject.toml`
- Optional dependency not installed

**Fix**:
1. Add missing dependency:
   ```bash
   # Add to pyproject.toml dependencies or requirements.txt
   pip install missing-package
   pip freeze > requirements-check.txt
   ```

2. Check optional dependencies:
   ```bash
   # Install with optional dependencies
   pip install -e ".[adk,dev]"
   ```

#### Test Timeout

**Error**: `pytest timeout` or tests hang

**Diagnosis**:
- Network calls blocking
- Infinite loops
- Resource contention

**Fix**:
1. Use test timeouts:
   ```bash
   pytest --timeout=30 tests/
   ```

2. Mock external services:
   ```python
   # Use pytest fixtures to mock HTTP calls
   @pytest.fixture
   def mock_rag_client():
       return MockRagClient()
   ```

### Linting and Formatting Issues

#### Ruff Errors

**Error**: `F401`, `F841`, `E722`, etc.

**Fix**:
```bash
# Auto-fix what can be fixed
ruff check --fix nvidia_blog_agent/ scripts/ service/ tests/

# Format code
ruff format nvidia_blog_agent/ scripts/ service/ tests/

# Check specific error types
ruff check --select F401,F841 nvidia_blog_agent/
```

#### Formatting Mismatch

**Error**: `Would reformat X files`

**Fix**:
```bash
# Format all files
ruff format .

# Verify formatting
ruff format --check .
```

### Secret Configuration Issues

#### Missing Secrets

**Error**: `Secret not found` or `undefined variable`

**Diagnosis**:
- GitHub secret not configured
- Secret name typo

**Fix**:
1. Verify secrets in GitHub:
   - Go to: Settings → Secrets and variables → Actions
   - Required secrets:
     - `WIF_PROVIDER`
     - `WIF_SERVICE_ACCOUNT`
     - `GCP_PROJECT_ID` (optional, defaults to `nvidia-blog-agent`)
     - `RAG_CORPUS_ID`
     - `INGEST_API_KEY`

2. Check secret names match workflow:
   ```yaml
   # In .github/workflows/deploy.yml
   workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
   # Must match exactly (case-sensitive)
   ```

### Network and Rate Limiting

#### API Rate Limits

**Error**: `429 Too Many Requests` or rate limit exceeded

**Diagnosis**:
- Too many requests to external APIs
- GitHub Actions rate limits

**Fix**:
1. Add retry logic (already implemented in code)
2. Use caching where possible
3. Reduce test frequency if hitting GitHub API limits

#### Timeout Errors

**Error**: `Request timeout` or `Connection timeout`

**Diagnosis**:
- Slow network
- External service unavailable
- Resource exhaustion

**Fix**:
1. Increase timeout in code:
   ```python
   # In httpx clients
   timeout=httpx.Timeout(30.0, connect=10.0)
   ```

2. Add retry logic (already implemented)
3. Check external service status

### Debugging Workflow Locally

#### Using Act (GitHub Actions Local Runner)

```bash
# Install act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Test CI workflow
act -j test

# Test deploy workflow (requires secrets)
act -j deploy --secret-file .secrets

# Dry run to see what would execute
act -n
```

#### Manual Workflow Steps

Reproduce workflow steps locally:

```bash
# 1. Checkout
git checkout master

# 2. Set up Python
python -m venv venv
source venv/bin/activate
pip install -e .

# 3. Run tests
pytest -v

# 4. Lint
ruff check nvidia_blog_agent/ scripts/ service/ tests/
ruff format --check .

# 5. Build Docker image
docker build -t nvidia-blog-agent:test .

# 6. Test Docker image
docker run -p 8080:8080 nvidia-blog-agent:test
```

### Getting Help

#### Logs and Diagnostics

1. **GitHub Actions Logs**:
   - Click on workflow run → failing job → expand steps
   - Look for error messages and stack traces

2. **Cloud Run Logs**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=nvidia-blog-agent" \
     --limit 100 \
     --format json
   ```

3. **Local Test Output**:
   ```bash
   pytest -v --tb=long tests/  # Verbose with full traceback
   ```

#### Common Solutions Checklist

Before asking for help, verify:

- [ ] All tests pass locally (`pytest`)
- [ ] Linting passes (`ruff check`)
- [ ] Formatting is correct (`ruff format --check`)
- [ ] Docker image builds locally (`docker build`)
- [ ] GitHub secrets are configured correctly
- [ ] Workload Identity Provider condition matches repo/branch
- [ ] Service account has required IAM roles
- [ ] Environment variables are set correctly

### Prevention

#### Pre-commit Hooks

Install pre-commit hooks to catch issues early:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

#### Local CI Simulation

Run CI checks locally before pushing:

```bash
# Run all CI checks
ruff check . && ruff format --check . && pytest
```

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

