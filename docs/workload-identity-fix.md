# Workload Identity Federation Fix Guide

## Problem

Error: `google-github-actions/auth failed with: failed to generate Google Cloud federated token ... {"error":"unauthorized_client","error_description":"The given credential is rejected by the attribute condition."}`

This means:
- ✅ GitHub issued an OIDC token correctly
- ✅ Google Cloud received the token
- ❌ The token failed the Workload Identity Provider's attribute condition

## Root Cause

The Workload Identity Provider's **Attribute Condition** doesn't match your actual repository and branch:
- **Your repo**: `TomBombadyl/nvidia_blog_agent`
- **Your branch**: `refs/heads/master`
- **Your workflow event**: `push`

The condition is likely set to a different repo/branch or uses incorrect attribute mappings.

## Solution: Fix in Google Cloud Console

### Step 1: Navigate to Workload Identity Federation

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project: `nvidia-blog-agent`
3. Navigate to: **IAM & Admin** → **Workload Identity Federation**
4. Find your **Workload Identity Pool** (the one for GitHub Actions)
5. Open the **Provider** (type = OIDC, issuer = `https://token.actions.githubusercontent.com`)

### Step 2: Verify Attribute Mapping

The provider must map these attributes correctly:

**Required Attribute Mappings:**

```
google.subject          → assertion.sub
attribute.repository    → assertion.repository
attribute.ref           → assertion.ref
attribute.actor         → assertion.actor
attribute.workflow      → assertion.workflow
attribute.environment    → assertion.environment
```

**Critical**: If `attribute.repository` or `attribute.ref` aren't mapped, any condition referencing them will fail.

### Step 3: Fix Attribute Condition

Set the **Attribute condition** to match your repository and branch:

**For master branch only:**
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& attribute.ref == "refs/heads/master"
```

**For master and main branches:**
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (attribute.ref == "refs/heads/master" || attribute.ref == "refs/heads/main")
```

**For any branch in the repo:**
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
```

**For branches and pull requests:**
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (startsWith(attribute.ref, "refs/heads/") || startsWith(attribute.ref, "refs/pull/"))
```

**Recommended (matches your workflow):**
```
attribute.repository == "TomBombadyl/nvidia_blog_agent"
&& (attribute.ref == "refs/heads/master" || attribute.ref == "refs/heads/main")
```

### Step 4: Save Changes

Click **Save** to apply the changes.

## Verify Workflow Configuration

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

**Required GitHub Secrets:**
- `WIF_PROVIDER`: Full resource name like:
  ```
  projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
  ```
- `WIF_SERVICE_ACCOUNT`: Service account email like:
  ```
  nvidia-blog-agent-sa@nvidia-blog-agent.iam.gserviceaccount.com
  ```

## Verify IAM Binding

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

## Debugging Steps

### 1. Temporarily Loosen Condition

To confirm the issue is the condition, temporarily set it to:
```
true
```

If the workflow succeeds, the problem is definitely the condition logic.

### 2. Tighten Step-by-Step

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

### 3. Check What Attributes Are Being Sent

You can't directly see the token contents, but you can verify by:
- Checking GitHub Actions logs for the auth step
- Temporarily using a permissive condition and checking Cloud Logging

## Quick Reference: Exact Values for This Project

- **Repository**: `TomBombadyl/nvidia_blog_agent`
- **Branches**: `master`, `main`
- **Ref format**: `refs/heads/master` or `refs/heads/main`
- **Event**: `push` (for automatic deployments)

## After Fixing

1. Save the Workload Identity Provider changes in GCP Console
2. Re-run the "Deploy to Cloud Run" workflow in GitHub Actions
3. The authentication step should now succeed ✅

## Common Mistakes

1. **Wrong repository name**: Using `TomBombadyl/nvidia-blog-agent` (with hyphen) instead of `TomBombadyl/nvidia_blog_agent` (with underscore)
2. **Wrong branch name**: Using `main` when the actual branch is `master` (or vice versa)
3. **Missing attribute mapping**: Not mapping `attribute.repository` or `attribute.ref` in the provider
4. **Case sensitivity**: Repository names are case-sensitive
5. **Extra spaces**: Attribute conditions are sensitive to whitespace

## Verification Checklist

- [ ] Workload Identity Provider attribute mappings include `attribute.repository` and `attribute.ref`
- [ ] Attribute condition matches `TomBombadyl/nvidia_blog_agent`
- [ ] Attribute condition includes `refs/heads/master` (or both master and main)
- [ ] Service account has `roles/iam.workloadIdentityUser` role
- [ ] GitHub secrets `WIF_PROVIDER` and `WIF_SERVICE_ACCOUNT` are set correctly
- [ ] Workflow has `permissions: id-token: write`
- [ ] Changes saved in GCP Console

