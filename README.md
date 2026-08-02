# NickLinney.AgentPod

**Project code:** NLSW000004

**Reference implementation:** AgentPod-RT1

**Delivery target:** MVP

**Repository status:** ARM64-validated development baseline; version and release remain unassigned

NickLinney.AgentPod is the standardized runtime environment for executing one autonomous agent. AgentPod-RT1 is the first reference implementation of that runtime contract; Docker, Ollama, and FastAPI are replaceable implementation choices rather than the AgentPod specification itself.

## MVP Delivery Boundary

The approved implementation is:

- local-first, with no cloud inference or SaaS dependency
- CPU-only
- Docker-native and OCI-oriented
- Debian Bookworm Slim based
- built from a pinned multi-architecture base; runtime validation is currently ARM64-only
- backed by local Ollama inference
- validated through the project-approved local Docker workflow

The MVP will ultimately provide the approved containerized runtime, essential REST API, intentionally small WebUI, health and status surfaces, configuration, authentication framework, telemetry, structured logging, persistent state, OpenAPI specification, and deployment documentation.

Kubernetes, GPU acceleration, multi-agent execution in one container, distributed memory, automatic model routing, federation, service mesh integration, multi-tenancy, high-availability clustering, marketplace integration, and advanced plugins are outside the MVP.

This project does not use repository CI, GitHub Actions, cloud actions, cloud runtime, or cloud testing. All testing is performed through the approved local Docker workflow.

## Current Support Status

The current feature-branch baseline provides a non-root local Docker application with the approved FastAPI health, status, and minimal chat surfaces, a replaceable Ollama boundary, locked Python packages, and secret-safe structured JSON application logs. It has been built and validated only through local Docker on ARM64 Apple Silicon. The pinned base image index includes both AMD64 and ARM64 manifests, but no AMD64 runtime build or test has been performed, so AMD64 runtime support is not yet validated.

The Ollama boundary is covered by controlled contract tests. No live Ollama service, model acquisition, or approved-model prompt-response execution has been performed, so live model compatibility is not claimed. No alternate environment, cloud runtime, or release validation has been performed.

## Repository Governance

- `main` is release-authoritative and is not a development surface.
- `dev` is the confirmed integration baseline.
- `test` is the rebuildable department-level validation surface.
- `staging` is a non-contributory UAT surface branching from `main` and never merges into `main`.
- `pre-alpha-1` is the initial scoped release vehicle; its existence does not authorize a release.
- `feature/agentpod-rt1-mvp` is the approved top-level MVP feature vehicle.
- Narrow sub-feature branches feed the top-level feature branch.
- Merges require PRs except work wholly within an agent's own personal development branch.
- Completed Dev tasks require named local Docker evidence, required review, a task-boundary commit, and prompt remote push.
- Successful validation never implies promotion, merge, version change, tag, or release authority.

Branch controls are governance-layer controls during MVP bootstrap. No GitHub technical branch protection is represented as active.

## Secrets and Project Records

Secrets, key files, credentials, governance records, meeting records, and external evidence do not belong in this repository. Local secret values must be supplied outside Git and must never be embedded in remote URLs, logs, documentation, commits, or evidence.

## Version and Release Status

The version is unassigned. The MVP is a delivery target, not an authorized release. No tag, GitHub release, version movement, or merge to `main` may be inferred from implementation or testing progress.
