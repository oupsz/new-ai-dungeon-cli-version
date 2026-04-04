# Release Notes

## Sanitization Summary

- Removed the hard-coded Firebase web API key from `ai_dungeon_cli/impl/api/client.py`
- The release now requires `AIDUNGEON_FIREBASE_API_KEY` to be provided by the user at runtime
- Excluded developer-only and machine-specific material such as `.git/`, local virtual environments, test suites, packaging leftovers, and workspace-specific launchers
- Replaced the original project documentation with a release-focused README written for Linux users

## Included Runtime Files

- `main.py`
- `ai_dungeon_cli/`
- `requirements.txt`
- `install.sh`
- `.gitignore`
- `README.md`
- `LICENSE`

## Excluded Files

- `tests/`
- `.git/`
- `venv/`
- `.venv-ai-dungeon-cli/`
- cache files
- temporary files
- machine-specific wrapper scripts outside the release package

## Security Confirmation

The release package was reviewed for secrets, tokens, passwords, API keys, cached credentials, and personal absolute paths. The hard-coded backend API key was removed from the release code. No personal credentials or machine-local launcher paths are included in this package.
