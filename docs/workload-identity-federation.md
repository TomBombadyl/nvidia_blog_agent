# Workload Identity Federation Guide

Complete guide for setting up and troubleshooting Workload Identity Federation (WIF) for GitHub Actions to Google Cloud authentication.

## Overview

Workload Identity Federation enables GitHub Actions to authenticate to Google Cloud without storing long-lived service account keys. It uses OIDC tokens issued by GitHub that are validated by Google Cloud.

```
GitHub Actions → OIDC Token → Workload Identity Provider → Service Account → Cloud Run
```

## Trust Chain

### Trust Chain Diagram

```
┌─────────────────┐
│  GitHub Actions  │
│  (Workflow Run)  │
└────────┬────────┘
         │
         │ 1. Request OIDC Token
         │    (with repo/branch/actor claims)
         ▼
┌─────────────────┐
│  GitHub OIDC    │
│  Token Issuer   │
│  (token.actions │
│  .github.com)   │
└────────┬────────┘
         │
         │ 2. Issue OIDC Token
         │    {
         │      "sub": "repo:TomBombadyl/nvidia_blog_agent:ref:refs/heads/master",
         │      "repository": "TomBombadyl/nvidia_blog_agent",
         │      "ref": "refs/heads/master",
         │      "actor": "TomBombadyl",
         │      "workflow": "Deploy to Cloud Run",
         │      ...
         │    }
         ▼
┌─────────────────┐
│  google-github- │
│  actions/auth   │
│  (GitHub Action)│
└────────┬────────┘
         │
         │ 3. Exchange OIDC Token
         │    for GCP Federated Token
         │    (via Workload Identity Provider)
         ▼
┌─────────────────────────────────┐
│  Google Cloud                   │
│  Workload Identity Provider     │
│  ┌───────────────────────────┐  │
│  │ Attribute Mapping:       │  │
│  │ - attribute.repository    │  │
│  │ - attribute.ref           │  │
│  │ - attribute.actor          │  │
│  │ - attribute.workflow       │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ Attribute Condition:       │  │
│  │ repository == "TomBomb...  │  │
│  │ && ref == "refs/heads/..." │  │
│  └───────────────────────────┘  │
└────────┬────────────────────────┘
         │
         │ 4. Validate Condition
         │    ✅ Repository matches
         │    ✅ Branch matches
         │    ✅ Issue Federated Token
         ▼
┌─────────────────┐
│  Service Account│
│  Impersonation  │
│  (nvidia-blog-  │
│   agent-sa@...) │
└────────┬────────┘
         │
         │ 5. Impersonate Service Account
         │    (with federated token)
         ▼
┌─────────────────┐
│  Google Cloud   │
│  APIs           │
│  - Cloud Run    │
│  - Artifact Reg │
│  - GCS          │
└─────────────────┘
```

### Step-by-Step Trust Flow

#### Step 1: GitHub Issues OIDC Token

When a GitHub Actions workflow runs with `permissions: id-token: write`:

```yaml
permissions:
  id-token: write  # Enables OIDC token issuance
  contents: read
```

GitHub automatically issues an OIDC token with claims about:
- Repository: `TomBombadyl/nvidia_blog_agent`
- Branch: `refs/heads/master`
- Actor: `TomBombadyl`
- Workflow: `Deploy to Cloud Run`
- Event: `push`

**Token Claims Example**:
```json
{
  "sub": "repo:TomBombadyl/nvidia_blog_agent:ref:refs/heads/master",
  "repository": "TomBombadyl/nvidia_blog_agent",
  "repository_owner": "TomBombadyl",
  "ref": "refs/heads/master",
  "sha": "9fdf922...",
  "workflow": "Deploy to Cloud Run",
  "actor": "TomBombadyl",
  "event_name": "push",
  "iss": "https://token.actions.githubusercontent.com",
  "aud": "//iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID"
}
```

#### Step 2: Workload Identity Provider Receives Token

The `google-github-actions/auth` action sends the OIDC token to Google Cloud:

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/.../providers/...
    service_account: nvidia-blog-agent-sa@...
```

Google Cloud receives the token and:
1. Validates the token signature (issued by GitHub)
2. Extracts claims from the token
3. Applies attribute mappings to create Google attributes

#### Step 3: Attribute Mapping

The Workload Identity Provider maps OIDC claims to Google attributes:

| OIDC Claim (assertion.*) | Google Attribute | Example Value |
|---------------------------|------------------|---------------|
| `assertion.sub` | `google.subject` | `repo:TomBombadyl/nvidia_blog_agent:ref:refs/heads/master` |
| `assertion.repository` | `attribute.repository` | `TomBombadyl/nvidia_blog_agent` |
| `assertion.ref` | `attribute.ref` | `refs/heads/master` |
| `assertion.actor` | `attribute.actor` | `TomBombadyl` |
| `assertion.workflow` | `attribute.workflow` | `Deploy to Cloud Run` |
| `assertion.environment` | `attribute.environment` | (if using environments) |

**Critical**: If `attribute.repository` or `attribute.ref` aren't mapped, conditions referencing them will always fail.

#### Step 4: Attribute Condition Evaluation

The provider evaluates the attribute condition:

```text
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (attribute.ref == "refs/heads/master" || attribute.ref == "refs/heads/main")
```

**Evaluation**:
- ✅ `attribute.repository` = `"TomBombadyl/nvidia_blog_agent"` → **MATCH**
- ✅ `attribute.ref` = `"refs/heads/master"` → **MATCH**
- ✅ Condition result: **TRUE**

If the condition evaluates to `true`, Google Cloud issues a federated token.

#### Step 5: Service Account Impersonation

The federated token is used to impersonate the service account:

```text
principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.repository/TomBombadyl/nvidia_blog_agent
```

This principal is granted the `roles/iam.workloadIdentityUser` role on the service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/.../attribute.repository/TomBombadyl/nvidia_blog_agent"
```

#### Step 6: Access Google Cloud APIs

The service account can now access Google Cloud APIs:
- Deploy to Cloud Run
- Push images to Artifact Registry
- Access GCS buckets
- Call Vertex AI APIs

All based on the service account's IAM roles.

## Setup and Configuration

### Step 1: Navigate to Workload Identity Federation

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project: `nvidia-blog-agent`
3. Navigate to: **IAM & Admin** → **Workload Identity Federation**
4. Find your **Workload Identity Pool** (the one for GitHub Actions)
5. Open the **Provider** (type = OIDC, issuer = `https://token.actions.githubusercontent.com`)

### Step 2: Configure Attribute Mapping

The provider must map these attributes correctly:

**Required Attribute Mappings**:

```
google.subject          → assertion.sub
attribute.repository    → assertion.repository
attribute.ref           → assertion.ref
attribute.actor         → assertion.actor
attribute.workflow      → assertion.workflow
attribute.environment    → assertion.environment
```

**Critical**: If `attribute.repository` or `attribute.ref` aren't mapped, any condition referencing them will fail.

### Step 3: Configure Attribute Condition

Set the **Attribute condition** to match your repository and branch:

**For master branch only**:
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& attribute.ref == "refs/heads/master"
```

**For master and main branches** (recommended):
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (attribute.ref == "refs/heads/master" || attribute.ref == "refs/heads/main")
```

**For any branch in the repo**:
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
```

**For branches and pull requests**:
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (startsWith(attribute.ref, "refs/heads/") || startsWith(attribute.ref, "refs/pull/"))
```

### Step 4: Configure GitHub Actions Workflow

Your GitHub Actions workflow (`.github/workflows/deploy.yml`) should have:

```yaml
permissions:
  contents: read
  id-token: write  # Required for OIDC

steps:
  - uses: actions/checkout@v4
  
  - id: auth
    uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
      service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}
```

**Required GitHub Secrets**:
- `WIF_PROVIDER`: Full resource name like:
  ```
  projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
  ```
- `WIF_SERVICE_ACCOUNT`: Service account email like:
  ```
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com
  ```

### Step 5: Configure IAM Binding

Ensure the service account has the Workload Identity User role:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.repository/TomBombadyl/nvidia_blog_agent"
```

Replace:
- `PROJECT_NUMBER`: Your GCP project number
- `POOL_ID`: Your Workload Identity Pool ID

## Troubleshooting

### Common Error: unauthorized_client

**Error**: `google-github-actions/auth failed with: failed to generate Google Cloud federated token ... {"error":"unauthorized_client","error_description":"The given credential is rejected by the attribute condition."}`

**What this means**:
- ✅ GitHub issued an OIDC token correctly
- ✅ Google Cloud received the token
- ❌ The token failed the Workload Identity Provider's attribute condition

### Root Cause

The Workload Identity Provider's **Attribute Condition** doesn't match your actual repository and branch:
- **Your repo**: `TomBombadyl/nvidia_blog_agent`
- **Your branch**: `refs/heads/master`
- **Your workflow event**: `push`

The condition is likely set to a different repo/branch or uses incorrect attribute mappings.

### Solution: Fix Attribute Condition

1. Navigate to Workload Identity Provider in GCP Console
2. Verify attribute mappings (see Step 2 above)
3. Update the attribute condition to match your repository and branch
4. Save changes

### Debugging Steps

#### 1. Temporarily Loosen Condition

To confirm the issue is the condition, temporarily set it to:
```
true
```

If the workflow succeeds, the problem is definitely the condition logic.

#### 2. Tighten Step-by-Step

1. First, test with only repository:
   ```
   attribute.repository == "TomBombadyl/nvidia_blog_agent"
   ```

2. Then add branch constraint:
   ```
   attribute.repository == "TomBombadyl/nvidia_blog_agent"
   && attribute.ref == "refs/heads/master"
   ```

3. Add more constraints as needed.

#### 3. Check What Attributes Are Being Sent

You can't directly see the token contents, but you can verify by:
- Checking GitHub Actions logs for the auth step
- Temporarily using a permissive condition and checking Cloud Logging

### Common Failure Points

#### 1. Missing Attribute Mapping

**Symptom**: Condition always fails, even with correct values

**Cause**: `attribute.repository` or `attribute.ref` not mapped

**Fix**: Add mapping in Workload Identity Provider

#### 2. Condition Mismatch

**Symptom**: `unauthorized_client` error

**Cause**: Condition doesn't match actual repo/branch

**Fix**: Update condition to match your repository

#### 3. Missing IAM Binding

**Symptom**: `Permission denied` when accessing APIs

**Cause**: Service account doesn't have `workloadIdentityUser` role

**Fix**: Add IAM binding with correct principalSet

#### 4. Wrong Provider Resource Name

**Symptom**: `Provider not found` error

**Cause**: `WIF_PROVIDER` secret has wrong resource name

**Fix**: Verify resource name matches GCP Console

### Common Mistakes

1. **Wrong repository name**: Using `TomBombadyl/nvidia-blog-agent` (with hyphen) instead of `TomBombadyl/nvidia_blog_agent` (with underscore)
2. **Wrong branch name**: Using `main` when the actual branch is `master` (or vice versa)
3. **Missing attribute mapping**: Not mapping `attribute.repository` or `attribute.ref` in the provider
4. **Case sensitivity**: Repository names are case-sensitive
5. **Extra spaces**: Attribute conditions are sensitive to whitespace

### Quick Reference: Exact Values for This Project

- **Repository**: `TomBombadyl/nvidia_blog_agent`
- **Branches**: `master`, `main`
- **Ref format**: `refs/heads/master` or `refs/heads/main`
- **Event**: `push` (for automatic deployments)

## Security Model

### Trust Boundaries

1. **GitHub → Google Cloud**: OIDC token proves the workflow run identity
2. **Google Cloud → Service Account**: Attribute condition restricts which workflows can impersonate
3. **Service Account → APIs**: IAM roles control what the service account can do

### Security Benefits

✅ **No long-lived keys**: No service account JSON keys stored in GitHub  
✅ **Fine-grained control**: Attribute conditions restrict by repo/branch/workflow  
✅ **Audit trail**: All actions are logged with the service account identity  
✅ **Automatic rotation**: OIDC tokens are short-lived and automatically rotated

### Attack Surface Reduction

**Before WIF** (Service Account Keys):
- ❌ Long-lived keys stored in GitHub secrets
- ❌ Keys can be leaked or stolen
- ❌ No way to restrict by repo/branch
- ❌ Keys must be manually rotated

**After WIF** (OIDC):
- ✅ Short-lived tokens (15 minutes)
- ✅ Tokens can't be reused outside the workflow
- ✅ Attribute conditions restrict access
- ✅ Automatic token rotation

## Verification

### Verification Checklist

- [ ] Workload Identity Provider attribute mappings include `attribute.repository` and `attribute.ref`
- [ ] Attribute condition matches `TomBombadyl/nvidia_blog_agent`
- [ ] Attribute condition includes `refs/heads/master` (or both master and main)
- [ ] Service account has `roles/iam.workloadIdentityUser` role
- [ ] GitHub secrets `WIF_PROVIDER` and `WIF_SERVICE_ACCOUNT` are set correctly
- [ ] Workflow has `permissions: id-token: write`
- [ ] Changes saved in GCP Console

### Verify Token Claims

You can't directly inspect the OIDC token, but you can verify by:
1. Temporarily setting condition to `true`
2. If it works, the issue is the condition
3. Tighten condition step-by-step

### Verify Attribute Mapping

In GCP Console:
1. Go to Workload Identity Provider
2. Check "Attribute mapping" section
3. Verify all required mappings exist

### Verify IAM Binding

```bash
# Check service account IAM policy
gcloud iam service-accounts get-iam-policy \
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com

# Should see:
# - roles/iam.workloadIdentityUser
# - member: principalSet://.../attribute.repository/TomBombadyl/nvidia_blog_agent
```

## After Fixing

1. Save the Workload Identity Provider changes in GCP Console
2. Re-run the "Deploy to Cloud Run" workflow in GitHub Actions
3. The authentication step should now succeed ✅

## Related Documentation

- [CI/CD Pipeline Documentation](ci-cd.md) - Pipeline configuration
- [Google Cloud WIF Documentation](https://cloud.google.com/iam/docs/workload-identity-federation)

