## Summary

## Verification

- [ ] `PYTHONPATH=. python -m pytest tests -q`
- [ ] `scripts/sanitize-check.sh`

## Safety

- [ ] No `config.json`, `.env`, auth files, credentials, task artifacts, queues,
      worktrees, or generated caches are committed.
- [ ] Public examples use generic repository names.
