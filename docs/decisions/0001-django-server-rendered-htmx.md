# 0001 — Django with server-rendered templates, HTMX and Alpine instead of an SPA

**Status:** accepted · **Date:** 2026-09-12

## Context

The tech-stack doc (`wonderkidz-tech-stack-v0.1.md`) argued for Django on three grounds: the auto-generated admin covers most of the operator tooling, auth/sessions/forms/ORM come for free, and server rendering is the native mode. SEO is a structural bet of the product: category and listing pages must be real crawlable HTML, and long-tail pages ("wooden toys for 2-year-olds in Saadat Abad") are generated from structured fields. The build was a six-week solo effort with weekly demos, so every layer had to maximise what comes for free. Next.js was the alternative on record and would have meant an admin from scratch and a less turnkey SSR story on domestic hosts.

## Decision

Django 5.1 with Django templates. Interactivity comes from two vendored libraries with no build step: **htmx** for server-driven updates (search results paging, phone reveal, chat polling every 4 s, panel approve/reject fragments) and **Alpine.js** for purely client-side state (the post-wizard stepper, upload previews, inline report forms). Every listing, category and static page is a full HTML response. A `request.htmx` flag (`apps/core/middleware.py`) lets a view return a fragment for htmx and a full page otherwise, so every htmx interaction has a plain-link fallback.

## Consequences

- Crawlable pages, JSON-LD and a sitemap were cheap; SEO work is template work.
- One deployable unit, one language, no Node in the build or the image.
- Real-time chat is polling; upgrading to SSE/WebSocket is a swap behind the same endpoints (see roadmap).
- Rich client state (the six-step wizard) is a single server form with Alpine over it; server-side validation errors reopen the failing step. Complex client interactions cost more here than they would in React, which is acceptable for a classifieds board.
- A native app later would add a JSON API (DRF) next to the templates, not replace them.
