# AGENTS.md

## What this repo is
sqlstratum-labs is a set of realistic stress-test and exploration apps for SQLStratum. These apps are not production templates.

## SQLStratum links
- GitHub: https://github.com/aognio/sqlstratum
- PyPI: https://pypi.org/project/sqlstratum/

## Repo map
- apps/clinicdesk
- scripts/ (if present)
- shared/ (if present)

## Development rules
- Keep changes focused to a single app or a small tooling/doc change.
- Never commit secrets.
- Prefer small PRs.

## Per-app virtualenv policy
Each app uses a local venv folder named `.env/` inside the app directory.

Example:
```bash
cd apps/clinicdesk
python -m venv .env
source .env/bin/activate
```

This keeps environments isolated per app and avoids a monorepo-wide venv.

## Local feedback and scratch space
Use `.feedback/` for raw notes, test outputs, screenshots, and issue observations that help during iterative development but should not be committed.

Use `.scrapbook/` for throwaway experiments, snippets, and work-in-progress artifacts while exploring ideas for an app. Keep both folders local to your machine and out of git.

## asdf recommendation
Use asdf to test multiple Python versions.

Minimal setup:
- Install asdf: https://asdf-vm.com/
- Add the Python plugin: `asdf plugin add python`
- Use `.tool-versions` to pin versions when needed.
