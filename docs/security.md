# Security documentation

See [the security plan](security-plan.md) for the existing anti-scraping plan and its implementation status.

Relevant implementation locations:

- Shared rate limiting: `common/security/rate_limits.py`
- Discussion interaction endpoints: `apps/discussions/views/interactions.py`
- Hosting authentication: `apps/hosting/api/decorators.py`
- Project access, tokens, quotas, and transfer checks: `apps/hosting/services/`
- Production configuration: `config/settings/production.py`

Planning notes are not a claim that every proposed control is implemented. Update this document and the plan when adding security behaviour.
