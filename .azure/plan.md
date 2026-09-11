# Azure Deployment Plan

> **Status:** Executing
>
> Generated: 2026-09-08

---

## 1. Project Overview

**Goal:** Move the Django/PostGIS API deployment path from Azure App Service to an existing user-created Azure Container App. Publish a one-off, feature-branch preview image to public GHCR first, use it to create and test the Container App, then deploy immutable live-merge images to it.

**Path:** Modernize Existing

---

## 2. Requirements

| Attribute | Value |
|-----------|-------|
| Classification | Production API; preview validation before cutover |
| Scale | Small (user has stated it is effectively read-only and used only by them) |
| Budget | Undetermined |
| Subscription | Existing subscription referenced by the GitHub Actions `AZURE_SUBSCRIPTION_ID` secret; confirmed by user |
| Location | UK South (`uksouth`, London); confirmed by user as suitable for database access |
| Resource group | `RCPCH-Dev-AuditTools` |
| Container App | `rcpch-nhs-organisations` |
| Preview branch | `python-bump-deploy-ghcr` |
| Registry | Private Azure Container Registry |
| Database | Existing live PostGIS database for the initial preview, per user decision |

---

## 3. Components Detected

| Component | Type | Technology | Path |
|-----------|------|------------|------|
| NHS organisations API | REST API | Django 5.2, Django REST Framework, GeoDjango, Gunicorn | `rcpch_nhs_organisations/` |
| Production image | Container | Python 3.12, GDAL/PROJ, Gunicorn | `Dockerfile.production` |
| CI/CD | GitHub Actions | Docker Buildx, GHCR, Azure OIDC | `.github/workflows/main_rcpch-nhs-organisations.yml` |
| Database | Relational GIS database | External PostgreSQL/PostGIS | Runtime configuration |

---

## 4. Recipe Selection

**Selected:** AZCLI / GitHub Actions

**Rationale:** The Container App will be created manually by the user and the existing project already uses an imperative GitHub Actions deployment workflow. No infrastructure-as-code is requested. The workflow needs only a preview-image bootstrap and an Azure Container Apps image update after live merges.

---

## 5. Architecture

**Stack:** Containers

### Service Mapping

| Component | Azure Service | SKU |
|-----------|---------------|-----|
| Django REST API | Azure Container Apps | User-managed existing Container Apps environment |
| Production container registry | GitHub Container Registry | Public package |
| GIS database | Existing PostgreSQL/PostGIS | Existing service |

### Supporting Services

| Service | Purpose |
|---------|---------|
| Azure Container Apps ingress | Public TLS termination and routing to container port 8000 |
| GitHub Actions OIDC identity | Authenticates the live workflow to update the Container App |
| Container App secrets | Holds Django secret key, database password, and postcode API key |

---

## 6. Execution Checklist

### Phase 1: Planning
- [x] Analyze workspace
- [x] Gather known requirements
- [x] Confirm resource group, Container App name, feature branch, and intended UK South location
- [x] Confirm use of the subscription referenced by `AZURE_SUBSCRIPTION_ID` and database network reachability
- [x] Scan codebase
- [x] Select recipe
- [x] Plan architecture
- [x] **User approved this plan**

### Phase 2: Execution
- [x] Add a feature-branch-only workflow that publishes `Dockerfile.production` to a unique `preview-<SHA>` GHCR tag without Azure deployment
- [ ] Configure the user-created Container App with the preview image, external HTTP ingress on port 8000, and runtime configuration
- [x] Replace the live App Service deployment job with an Azure Container Apps update job that deploys the immutable `sha-<merge-SHA>` image
- [x] Preserve an explicit migration procedure; do not run migrations in the web container command
- [x] Correct the production Dockerfile to copy only template directories that exist in the repository
- [ ] Remove the temporary preview workflow after bootstrap
- [ ] Update plan status to "Ready for Validation" after the Container App preview configuration is complete

### Phase 3: Validation
- [ ] Invoke azure-validate skill
- [ ] All validation checks pass
- [ ] Update plan status to "Validated"
- [ ] Record validation proof below

### Phase 4: Deployment
- [ ] Invoke azure-deploy skill
- [ ] Deployment successful
- [ ] Update plan status to "Deployed"

---

## 7. Validation Proof

> The azure-validate skill must populate this section before setting status to `Validated`.

| Check | Command Run | Result | Timestamp |
|-------|-------------|--------|-----------|
| Workflow YAML parsing | `ruby -e 'require "yaml"; ...' .github/workflows/main_rcpch-nhs-organisations.yml .github/workflows/publish-container-preview.yml` | Pass | 2026-09-08 |
| Workflow/Dockerfile whitespace | `ruby -e '... trailing-space check ...'` | Pass | 2026-09-08 |
| Production image build | `docker build --file Dockerfile.production --tag rcpch-nhs-organisations:workflow-validation --build-arg GIT_SHA=workflow-validation .` | Pass | 2026-09-08 |
| Image runtime contract | `docker image inspect --format '{{json .Config.Cmd}} {{json .Config.ExposedPorts}}' rcpch-nhs-organisations:workflow-validation` | Pass — Gunicorn command and `8000/tcp` present | 2026-09-08 |
| Azure CLI command availability | `az containerapp update --help` | Pass | 2026-09-08 |

> Full Azure validation remains pending until the Container App has been created and configured with the preview image.

---

## 8. Files to Generate

| File | Purpose | Status |
|------|---------|--------|
| `.azure/plan.md` | Deployment plan | Complete |
| `.github/workflows/publish-container-preview.yml` | Temporary feature-branch preview-image publisher | Complete |
| `.github/workflows/main_rcpch-nhs-organisations.yml` | Replace App Service deployment job with Container Apps update | Complete |
| `Dockerfile.production` | Remove nonexistent root-level template-directory copy that blocked GHCR builds | Complete |

---

## 9. Next Steps

> Current: Configure and validate the user-created Container App using the preview image.

1. Push the feature branch and wait for the preview image to publish to GHCR.
2. Create/configure the Container App using the preview image, then validate it.
3. Remove the temporary preview workflow before merging the feature branch to `live`.
