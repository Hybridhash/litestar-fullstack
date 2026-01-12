# Security Notes

This document tracks current safeguards and planned improvements for the server-rendered HTMX stack.

## Current safeguards

- Superuser guards protect user-management endpoints.
- Query, sort, and order inputs are normalized and validated in `src/app/domain/web/table_helpers.py`.
- User/team display strings and confirmation prompts are sanitized with `nh3` and escaped before HTML injection.

## Planned improvements

- [ ] Add CSRF protection for HTMX requests (token injection + server validation).
- [ ] Add rate limiting for list endpoints to reduce enumeration/DoS risk.
- [ ] Add audit logging for sensitive actions (user create/delete, role changes).
- [ ] Review secure cookie flags for auth cookies in production.
- [ ] Add input validation for search/query params at the API boundary.

## Notes

- After adding `nh3` to dependencies, run `uv sync` to install it locally.
