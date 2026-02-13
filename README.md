# sqlstratum-labs

<p align="center">
  <img src="https://raw.githubusercontent.com/aognio/sqlstratum/main/assets/images/SQLStratum-Logo-500x500-transparent.png" alt="SQLStratum logo" />
</p>

A monorepo of stress-test and exploration apps for SQLStratum. These apps are designed to exercise joins, aggregates, pagination, search, and transactions in realistic flows, not to serve as production templates.

Links:
- [SQLStratum (GitHub)](https://github.com/aognio/sqlstratum)
- [SQLStratum (PyPI)](https://pypi.org/project/sqlstratum/)

## Getting started (ClinicDesk)

1. `cd apps/clinicdesk`
2. `python -m venv .env`
3. `source .env/bin/activate`
4. `pip install -r requirements.txt`
5. `pip install sqlstratum`
6. `python scripts/seed.py`
7. `./run.sh`

Open `http://127.0.0.1:5001`.

asdf (optional) for testing multiple Python versions:
- Install asdf: https://asdf-vm.com/
- `asdf plugin add python`
- Use `.tool-versions` when you want to pin a version.

## Contributing / feedback

PRs and DX feedback are welcome. These apps are intended for stress testing SQLStratum behavior (joins, aggregates, pagination, search, and transactions), so keep changes focused and pragmatic.
