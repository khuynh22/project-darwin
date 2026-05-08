# Security policy

## Supported versions

Project Darwin is research software in active development. Only `main` is supported. Security fixes are applied to `main`; there are no LTS branches.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately via GitHub's [Security Advisories](https://github.com/khuynh22/project-darwin/security/advisories/new) on this repository. Title the report `[security] <short description>` so it's easy to triage.

Please include:
- A description of the issue and its impact
- Reproduction steps or a proof-of-concept
- Affected commit SHA or tag
- Your suggested remediation, if any

You should receive an acknowledgement within **5 business days**. Coordinated disclosure timelines are negotiated case-by-case based on severity and availability of a fix.

## Scope

In scope:
- The FastAPI Oracle (`backend/app/`)
- The Next.js arena (`frontend/`)
- API-key storage, encryption, and the `/api-keys` endpoints
- The Postgres schema and migration logic
- The WebSocket broadcaster

Out of scope:
- Issues that require a malicious operator (this is a self-hosted tool — the operator is trusted)
- Vulnerabilities in third-party LLM provider APIs themselves
- Best-practice hardening suggestions with no concrete attack (file an issue or PR for those)
- Stub-mode-only issues that don't affect real-key deployments

## Handling API keys

When working on or deploying Project Darwin:

- Keys can be stored encrypted in the database (Fernet, see `backend/app/models/api_key.py`). Set `ENCRYPTION_KEY` in `.env` so keys survive restarts.
- Without `ENCRYPTION_KEY`, an ephemeral key is generated at startup — stored keys are unreadable after a restart.
- `.env` is gitignored. Never commit real keys.
- The `/api-keys` endpoints never return raw keys; only metadata.

If you discover a path that exposes raw API keys (logs, error responses, network frames, etc.), treat it as a vulnerability and report it privately.
