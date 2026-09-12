# WonderKidz Web — documentation

Documentation for the WonderKidz classifieds platform. It is organised by concern so it can grow: each file answers one kind of question, `decisions/` records why things are the way they are, and `roadmap.md` records what is deliberately not built yet. Product planning (briefs, stakeholder defaults, UI mockups, research) stays in the sibling [wonderkidz-planning](https://github.com/mohsp-99/wonderkidz-planning) repo; this folder documents the software.

## Start here

| I want to… | Read |
|---|---|
| Run it locally in five minutes | [getting-started.md](getting-started.md) |
| Understand how the code is organised and how a request flows | [architecture.md](architecture.md) |
| Know what the data looks like and how a listing moves through its states | [data-model.md](data-model.md) |
| Understand the design system, RTL rules, and front-end behaviours | [frontend.md](frontend.md) |
| See how search, filters, and SEO pages work | [search-and-seo.md](search-and-seo.md) |

## Product behaviour

| Topic | Read |
|---|---|
| Review models, automatic checks, operator panel actions, bans | [moderation.md](moderation.md) |
| SMS/OTP, payment gateways, media storage — the plug-and-play backends | [integrations.md](integrations.md) |
| Persian ↔ English vocabulary with code identifiers | [glossary.md](glossary.md) |

## Running it for real

| Topic | Read |
|---|---|
| Environments, Docker, env vars, CI, first deploy, legacy URL redirects | [deployment.md](deployment.md) |
| Day-2 runbook: commands, backups, monitoring, troubleshooting | [operations.md](operations.md) |
| Running and writing tests, visual checks with headless Chrome | [testing.md](testing.md) |

## Why and what next

| Topic | Read |
|---|---|
| Architecture decision records (ADRs) | [decisions/](decisions/README.md) |
| Post-MVP roadmap with readiness of each item | [roadmap.md](roadmap.md) |

## Conventions for this folder

- One concern per file; add a new file rather than growing an unrelated one. Register it in this index.
- Every file opens with a one-paragraph summary and a `Related:` line linking siblings.
- A decision that changes architecture, data, or an external dependency gets an ADR in `decisions/` (template inside). Docs describe the current state; ADRs keep the history.
- Docs describe what the code does today. Anything planned but not built belongs in `roadmap.md`, marked with its readiness.
- User-facing Persian strings are quoted as they appear in the UI; prose is English.
- Suggested future homes as the project grows: `docs/api/` when a JSON API ships, `docs/runbooks/` for incident-specific procedures, `docs/design/` for screen specs beyond the mockups.
