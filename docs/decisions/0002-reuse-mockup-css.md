# 0002 — Reuse the mockup CSS design system instead of Tailwind

**Status:** accepted · **Date:** 2026-09-12

## Context

The tech-stack doc listed Tailwind CSS for styling. By the time the build started, the planning repo's `ui-mockups/` contained a complete hand-written design system (`styles.css`, ~1100 lines: tokens, buttons, forms, chips/badges, header/footer, cards, search/detail/post/chat/auth/profile/admin layouts, responsive rules) plus nine static mockups that stakeholders had reviewed. Rebuilding the same visuals in Tailwind utility classes would have cost days and risked drifting from the signed-off screens.

## Decision

Copy `ui-mockups/styles.css` verbatim into `static/css/styles.css` and treat it as the design system. Additions specific to the app (real `<img>` inside placeholders, htmx indicators, form error states, upload slots, layout guards) go in `static/css/app.css` and nothing else. Templates reuse the mockup class names and Persian copy one to one. The Vazirmatn font is self-hosted (`static/fonts/`) and declared with a single `@font-face` prepended to the stylesheet; the mockups' Google Fonts link is gone.

## Consequences

- Pages match the mockups closely enough to compare screenshots side by side (see `testing.md`).
- No CSS build step, no PostCSS, no purge configuration.
- Changes to the design system happen in one plain CSS file; a future designer edits tokens, not utility strings.
- The mockups' `index.html` presentation-hub styles (section 19 of the stylesheet) are dead weight in production and can be removed when convenient.
- If the team later standardises on Tailwind, the migration is a template-by-template rewrite; the component vocabulary (`.card`, `.badge-*`, `.ph-*`, `.q-item`) documents what would need equivalents.
